import unittest

class GammaDeskSuite(unittest.TestCase):
    panid = 1

    def test_code_1(self):
        from gdesk import gui
        import numpy as np
        import scipy.misc
        
        print('Hello World')
        for i in range(10):
            print(i)        
        
        arr = scipy.misc.face()
        gui.show(arr)
        gui.img.zoom_fit()
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Flip Horizontal'])
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Flip Vertical'])
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Rotate 180'])
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Image', 'to Monochroom'])
        gui.img.cmap('turbo')
        
    def test_code_2(self):
        from pylab import plt
        
        plt.plot(gui.vs.mean(1))
        plt.grid(True)
        plt.title('Column Means')
        plt.show()
        plt.figure()
        plt.plot(gui.vs.mean(0))
        plt.grid(True)
        plt.title('Row Means')
        plt.show()

        input('Press Enter to continue')

        plt.close('all')
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Edit', 'Show Prior Image'])
        
def suite():
    suite = unittest.TestSuite()
    suite.addTest(GammaDeskSuite('test_code_1'))
    suite.addTest(GammaDeskSuite('test_code_2'))
    return suite

runner = unittest.TextTestRunner()
runner.run(suite())        
