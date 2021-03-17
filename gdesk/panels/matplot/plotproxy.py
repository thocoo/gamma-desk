import pickle

import pylab

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui

class FigureBox(object):
    def __init__(self, figure):
        self.figure = figure
        
    def __getstate__(self):
        state = dict()
        mgr = self.figure.canvas.manager
        self.figure.canvas.manager = None
        state['figure'] = pickle.dumps(self.figure)
        self.figure.canvas.manager = mgr
        return state
        
    def __setstate__(self, state):
        self.figure = pickle.loads(state['figure'])  
        
class PlotProxy(object):
    def __init__(self, gui):
        self.gui = gui        
        
    def __dir__(self):        
        return dir(pylab)
        
    def __getattr__(self, attr):
        func = getattr(pylab, attr)
        return lambda *args, **kwargs: self.gui.gui_call(func, *args, **kwargs)          
       
class PlotGuiProxy(GuiProxyBase):    
    category = 'plot'
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.plot = self    
        gui.prepareplot = self.prepareplot
        self.plx = PlotProxy(gui) 
          
    def show(self, figure=None, hold=False):    
        import matplotlib.pyplot as plt           
        
        from matplotlib.figure import Figure        

        if not gui._qapp is None:
            if figure is None:
                plt.show()
            else:
                plt.figure(figure.number)
                plt.show()
            return
            
        if figure is None:
            figure = plt.gcf()            
       
        assert isinstance(figure, Figure)
        return self.show_figure_box(FigureBox(figure), hold) 
        
    def prepareplot(self):
        return self.plx    

    @StaticGuiCall
    def select(panid=-1, args=()):
        """
        If panid < 0, -1: select the active panel, -2: selected before that, ...
        panid == None: new panel
        panid >= 0: select the panel if exists, otherwise a new with that number
        """    
        panel = gui.qapp.panels.select_or_new('plot', panid, 'basic', args=args)
        return panel.panid
        
    @StaticGuiCall
    def restore_gcf_set_active():
        from . import plotpanel
        plotpanel.restore_gcf_set_active()

    @StaticGuiCall
    def new(figure_id=None):
        """
        Create a new figure.
        
        Links to pylab.figure
        """ 
        import matplotlib.pyplot as plt
        fig = plt.figure(figure_id)
        return fig, fig.number 

    def xy(self, *args, **kwargs):
        if not kwargs.get('hold', False):
            self.plx.figure()
        if 'hold' in kwargs.keys():
            kwargs.pop('hold')
        self.plx.plot(*args, **kwargs)
        self.plx.show()

    @StaticGuiCall  
    def show_figure_box(figurebox, hold=False):
        """
        Display the figure in the figurebox.
        The figure has to be added to the current pyplot backend.            
        
        :param bool hold: Replace the figure in the current selected panel by the new figure
        """
        #unpickling a figure will call show when interactive is on
        #But this will be on the backend of the pickling process 
        #All callbacks related to gui calls where removed by the pickling
        #
        
        from ...matplotbe import new_figure_manager_given_figure
        
        import matplotlib.pyplot as plt
        import matplotlib._pylab_helpers as pylab_helpers
                
        fig = figurebox.figure 

        def make_active(event):
            pylab_helpers.Gcf.set_active(mgr)                     
        
        if False:
            #Creating a new figure manager
            allnums = plt.get_fignums()
            num = max(allnums) + 1 if allnums else 1      
            
            mgr = new_figure_manager_given_figure(num, fig)                                    
            mgr._cidgcf = mgr.canvas.mpl_connect('button_press_event',
                                                     make_active)
                                      
            pylab_helpers.Gcf.set_active(mgr)
            fig = mgr.canvas.figure
            fig.number = num
            
            mgr.show()
        
        else:
            #Use the current figure mamaner and plot panel
            # Try to replace the figure on the current plot panel with this new figure
            from ...matplotbe import FigureCanvasGh2
            panids = gui.get_panel_ids('plot')                       
            
            if not hold or len(panids) == 0:
                ignore, num = PlotGuiProxy.new()
            else:
                num = panids[-1]
            
            plotpanel = gui.qapp.panels['plot'][num]
            fig.number = num            
            plotpanel.showNewFigure(fig)                        
            
            #Hack to call the correct set_active
            #Note that Gcf.set_active() is mapped to panel.select() in plotpanel.py
            mgr = fig.canvas.manager
            mgr._cidgcf = mgr.canvas.mpl_connect('button_press_event', make_active) 
            
            plotpanel.show()
        
        # I don't get the interactive update working
        # After a function lik grid(), xlabel(), ..
        # the stale property is set to  True
        # This should trigger the call of stale_callback on the figure (=Artist)
        # or stall_callback on the axis object
        
        #Configure stale call backs
        #The hierarchy of the figure can be type of figure dependend        
        try:
            from matplotlib.pyplot import _auto_draw_if_interactive
            from matplotlib.figure import _stale_figure_callback
            from matplotlib.artist import _stale_axes_callback
        
            fig.stale_callback = _auto_draw_if_interactive
        
            for ax in fig.axes:
                ax.stale_callback = _stale_figure_callback
                ax.xaxis.stale_callback = _stale_axes_callback
                ax.yaxis.stale_callback = _stale_axes_callback
        except:
            logger.error('Could not configure all interactive callbacks')
            
        return num    