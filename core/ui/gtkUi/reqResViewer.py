'''
reqResViewer.py

Copyright 2008 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

'''
import gtk
from . import entries

# To show request and responses
from core.data.db.reqResDBHandler import reqResDBHandler

useMozilla = False
useGTKHtml2 = False

try:
    import gtkmozembed
    withMozillaTab = True
except Exception, e:
    withMozillaTab = False

try:
    import gtkhtml2
    withGtkHtml2 = True
except Exception, e:
    withGtkHtml2 = False

# Signal handler to handle SIGSEGV generated by gtkhtml2
import signal
def sigsegv_handler(signum, frame):
    print _('This is a catched segmentation fault!')
    print _('I think you hitted bug #1933524 , this is mainly a gtkhtml2 problem. Please report this error here:')
    print _('https://sourceforge.net/tracker/index.php?func=detail&aid=1933524&group_id=170274&atid=853652')
signal.signal(signal.SIGSEGV, sigsegv_handler)
# End signal handler
    
class reqResViewer(gtk.VBox):
    '''
    A widget with the request and the response inside.

    @author: Andres Riancho ( andres.riancho@gmail.com )
    @author: Facundo Batista ( facundo@taniquetil.com.ar )
    '''
    def __init__(self, w3af, enableWidget=None, withManual=True, withFuzzy=True, withCompare=True, editableRequest=False, editableResponse=False, widgname="default"):
        super(reqResViewer,self).__init__()
        self.w3af = w3af
        
        pan = entries.RememberingHPaned(w3af, "pane-reqRV"+widgname, 400)
        pan.show()
        self.pack_start(pan)

        # request
        self.request = requestPaned(w3af, enableWidget, editable=editableRequest, widgname=widgname)
        self.request.show()
        pan.pack1(self.request.notebook)

        # response
        self.response = responsePaned(w3af, editable=editableResponse, widgname=widgname)
        self.response.show()
        pan.pack2(self.response.notebook)

        # buttons
        if withManual or withFuzzy or withCompare:
            from .craftedRequests import ManualRequests, FuzzyRequests
            hbox = gtk.HBox()
            if withManual:
                b = entries.SemiStockButton("", gtk.STOCK_INDEX, _("Send Request to Manual Editor"))
                b.connect("clicked", self._sendRequest, ManualRequests)
                self.request.childButtons.append(b)
                b.show()
                hbox.pack_start(b, False, False, padding=2)
            if withFuzzy:
                b = entries.SemiStockButton("", gtk.STOCK_PROPERTIES, _("Send Request to Fuzzy Editor"))
                b.connect("clicked", self._sendRequest, FuzzyRequests)
                self.request.childButtons.append(b)
                b.show()
                hbox.pack_start(b, False, False, padding=2)
            if withCompare:
                b = entries.SemiStockButton("", gtk.STOCK_ZOOM_100, _("Send Request and Response to Compare Tool"))
                b.connect("clicked", self._sendReqResp)
                self.response.childButtons.append(b)
                b.show()
                hbox.pack_end(b, False, False, padding=2)
            self.pack_start(hbox, False, False, padding=5)
            hbox.show()

        self.show()

    def _sendRequest(self, widg, func):
        '''Sends the texts to the manual or fuzzy request.

        @param func: where to send the request.
        '''
        up,dn = self.request.getBothTexts()
        func(self.w3af, (up,dn))

    def _sendReqResp(self, widg):
        '''Sends the texts to the compare tool.'''
        requp,reqdn = self.request.getBothTexts()
        self.w3af.mainwin.commCompareTool((requp, reqdn, self.response.showingResponse))

class requestResponsePaned(entries.RememberingVPaned):
    def __init__(self, w3af, enableWidget=None, editable=False, widgname="default"):
        entries.RememberingVPaned.__init__(self, w3af, "pane-rRVreqRespPane"+widgname)
        self.childButtons = []

        # The textview where a part of the req/res is showed
        self._upTv = searchableTextView()
        self._upTv.set_editable(editable)
        self._upTv.set_border_width(5)
        if enableWidget:
            self._upTv.get_buffer().connect("changed", self._changed, enableWidget)
            for widg in enableWidget:
                widg(False)
        
        # The textview where a part of the req/res is showed (this is for postdata and response body)
        self._downTv = searchableTextView()
        self._downTv.set_editable(editable)
        self._downTv.set_border_width(5)
        
        # vertical pan (allows resize of req/res texts)
        self.pack1( self._upTv )
        self.pack2( self._downTv )
        self.show()

    def set_sensitive(self, how):
        '''Sets the pane on/off.

        This is not a camelcase name to match the GTK interface.
        '''
        self.notebook.set_sensitive(how)
        for but in self.childButtons:
            but.set_sensitive(how)

    def _changed(self, widg, toenable):
        '''Supervises if the widget has some text.'''
        uppBuf = self._upTv.get_buffer()
        uppText = uppBuf.get_text(uppBuf.get_start_iter(), uppBuf.get_end_iter())
        for widg in toenable:
            widg(bool(uppText))
        
    def _clear( self, textView ):
        '''
        Clears a text view.
        '''
        buff = textView.get_buffer()
        start, end = buff.get_bounds()
        buff.delete(start, end)
        
    def clearPanes(self):
        '''Public interface to clear both panes.'''
        self._clear( self._upTv )
        self._clear( self._downTv )

    def showError(self, text):
        '''Show an error.
        
        Errors are shown in the upper part, with the lower one greyed out.
        '''
        self._clear(self._upTv)
        buff = self._upTv.get_buffer()
        iter = buff.get_end_iter()
        buff.insert(iter, text)
        
        self._clear(self._downTv)
        self._downTv.set_sensitive(False)
        
    def getBothTexts(self):
        '''Returns the upper and lower texts.'''
        uppBuf = self._upTv.get_buffer()
        uppText = uppBuf.get_text(uppBuf.get_start_iter(), uppBuf.get_end_iter())
        lowBuf = self._downTv.get_buffer()
        lowText = lowBuf.get_text(lowBuf.get_start_iter(), lowBuf.get_end_iter())
        return (uppText, lowText)


class requestPaned(requestResponsePaned):
    def __init__(self, w3af, enableWidget=None, editable=False, widgname="default"):
        requestResponsePaned.__init__(self, w3af, enableWidget, editable, widgname+"request")

        self.notebook = gtk.Notebook()
        l = gtk.Label("Request")
        self.notebook.append_page(self, l)
        
        self.notebook.show()
        self.show()
        
    def showObject(self, fuzzableRequest):
        '''
        Show the data from a fuzzableRequest object in the textViews.
        '''
        self.showingRequest = fuzzableRequest
        head = fuzzableRequest.dumpRequestHead()
        postdata = fuzzableRequest.getData()

        self._clear(self._upTv)
        buff = self._upTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, head)
        
        self._downTv.set_sensitive(True)
        self._clear(self._downTv)
        buff = self._downTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, postdata)
        
    def showParsed( self, method, uri, version, headers, postData ):
        '''
        Show the data in the corresponding order in self._upTv and self._downTv
        
        FIXME: This method AIN'T USED. Please deprecate in the future!
        '''
        # Clear previous results
        self._clear( self._upTv )
        self._clear( self._downTv )
        
        buff = self._upTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert( iterl, method + ' ' + uri + ' ' + 'HTTP/' + version + '\n')
        buff.insert( iterl, headers )
        
        buff = self._downTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert( iterl, postData )
    
    def rawShow(self, requestresponse, body):
        '''Show the raw data.'''
        self._clear(self._upTv)
        buff = self._upTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, requestresponse)
        
        self._downTv.set_sensitive(True)
        self._clear(self._downTv)
        buff = self._downTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, body)
        
class responsePaned(requestResponsePaned):
    def __init__(self, w3af, editable=False, widgname="default"):
        requestResponsePaned.__init__(self, w3af, editable=editable, widgname=widgname+"response")
        self.notebook = gtk.Notebook()
        self.showingResponse = None

        # first page
        l = gtk.Label("Response")
        self.notebook.append_page(self, l)
        self.notebook.show()

        # second page, only there if html renderer available
        self._renderingWidget = None
        if (withMozillaTab and useMozilla) or (withGtkHtml2 and useGTKHtml2):
            if withGtkHtml2 and useGTKHtml2:
                renderWidget = gtkhtml2.View()
                self._renderFunction = self._renderGtkHtml2
            elif withMozillaTab and useMozilla:
                renderWidget = gtkmozembed.MozEmbed()
                self._renderFunction = self._renderMozilla
            else:
                renderWidget = None
                
            self._renderingWidget = renderWidget
            if renderWidget is not None:
                swRenderedHTML = gtk.ScrolledWindow()
                swRenderedHTML.add(renderWidget)
                self.notebook.append_page(swRenderedHTML, gtk.Label(_("Rendered response")))
        
        self.show()

    def _renderGtkHtml2(self, body, mimeType, baseURI):
        # It doesn't make sense to render something empty
        if body != '':
            try:
                document = gtkhtml2.Document()
                document.clear()
                document.open_stream(mimeType)
                document.write_stream(body)
                document.close_stream()
                self._renderingWidget.set_document(document)
            except ValueError, ve:
                # I get here when the mime type is an image or something that I can't display
                pass
            except Exception, e:
                print _('This is a catched exception!')
                print _('Exception:'), type(e), str(e)
                print _('I think you hitted bug #1933524 , this is mainly a gtkhtml2 problem. Please report this error here:')
                print _('https://sourceforge.net/tracker/index.php?func=detail&aid=1933524&group_id=170274&atid=853652')

    def _renderMozilla(self, body, mimeType, baseURI):
        self._renderingWidget.render_data(body, long(len(body)), baseURI , mimeType)
        

    def showObject(self, httpResp):
        '''
        Show the data from a httpResp object in the textViews.
        '''

        self.showingResponse = httpResp
        resp = httpResp.dumpResponseHead()
        body = httpResp.getBody()

        self._clear(self._upTv)
        buff = self._upTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, resp)
        
        self._downTv.set_sensitive(True)
        self._clear(self._downTv)
        buff = self._downTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert(iterl, body)

    def showParsed( self, version, code, msg, headers, body, baseURI ):
        '''
        Show the data in the corresponding order in self._upTv and self._downTv
        '''
        # Clear previous results
        self._clear( self._upTv )
        self._clear( self._downTv )

        buff = self._upTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert( iterl, 'HTTP/' + version + ' ' + str(code) + ' ' + str(msg) + '\n')
        buff.insert( iterl, headers )
        
        # Get the mimeType from the response headers
        mimeType = 'text/html'
        headers = headers.split('\n')
        headers = [h for h in headers if h]
        for h in headers:
            h_name, h_value = h.split(':', 1)
            if 'content-type' in h_name.lower():
                mimeType = h_value.strip()
                break
        
        # FIXME: Show images
        if 'image' in mimeType:
            mimeType = 'text/html'
            body = _('The response type is: <i>') + mimeType + _('</i>. w3af is still under development, in the future images will be displayed.')
            
        buff = self._downTv.get_buffer()
        iterl = buff.get_end_iter()
        buff.insert( iterl, body )
        
        # Show it rendered
        if self._renderingWidget is not None:
            self._renderFunction(body, mimeType, baseURI)


class searchableTextView(gtk.VBox, entries.Searchable):
    '''A textview widget that supports searches.

    @author: Andres Riancho ( andres.riancho@gmail.com )
    '''
    def __init__(self):
        gtk.VBox.__init__(self)
        
        # Create the textview where the text is going to be shown
        self.textView = gtk.TextView()
        self.textView.show()
        
        # Scroll where the textView goes
        sw1 = gtk.ScrolledWindow()
        sw1.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw1.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw1.add(self.textView)
        sw1.show()
        self.pack_start(sw1, expand=True, fill=True)
        self.show()
        
        # Create the search widget
        entries.Searchable.__init__(self, self.textView, small=True)
    
    def set_editable(self, e):
        return self.textView.set_editable(e)
        
    def set_border_width(self, b):
        return self.textView.set_border_width(b)
        
    def get_buffer(self):
        return self.textView.get_buffer()

class reqResWindow(entries.RememberingWindow):
    '''
    A window to show a request/response pair.
    '''
    def __init__(self, w3af, request_id, enableWidget=None, withManual=True,
                 withFuzzy=True, withCompare=True, editableRequest=False, 
                 editableResponse=False, widgname="default"):
        # Create the window
        entries.RememberingWindow.__init__(
            self, w3af, "reqResWin", _("w3af - HTTP Request/Response"), "Browsing_the_Knowledge_Base")

        # Create the request response viewer
        rrViewer = reqResViewer(w3af, enableWidget, withManual, withFuzzy, withCompare, editableRequest, editableResponse, widgname)

        # Search the id in the DB
        dbh = reqResDBHandler()
        search_result = dbh.searchById( request_id )
        if len(search_result) == 1:
            request, response = search_result[0]

        # Set
        rrViewer.request.showObject( request )
        rrViewer.response.showObject( response )
        rrViewer.show()
        self.vbox.pack_start(rrViewer)

        # Show the window
        self.show()

