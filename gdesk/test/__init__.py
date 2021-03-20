import unittest

class GammaDeskSuite(unittest.TestCase):
    panid = 1
    
    def test_screenstate_1(self):
        from gdesk import gui
        from pylab import plt
        from pathlib import Path

        gui.load_layout('console')

        samplePath = Path(r'./samples')

        gui.img.select(1)
        gui.img.open(samplePath / 'kodim05.png')
        gui.img.zoom_fit()
        plt.plot(gui.vs.mean(2).mean(1))
        plt.title('Column means of image 1')
        plt.xlabel('Column Number')
        plt.ylabel('Mean')
        plt.grid()
        plt.show()

        gui.img.select(2)
        gui.img.open(samplePath / 'kodim23.png')
        gui.img.zoom_full()
        plt.figure()
        plt.plot(gui.vs.mean(2).mean(0))
        plt.title('Row means of image 2')
        plt.xlabel('Row Number')
        plt.ylabel('Mean')
        plt.grid()
        plt.show()


    def test_small_loop_and_print(self):
        from gdesk import gui
        import time
        
        gui.clc()
        
        expectedOutput = ''

        for i in range(42):
            line = f'i = {i}'
            print(line)       
            expectedOutput += f'{line}\n'
            time.sleep(0.01)
            
        text = gui.console.text()
        assert expectedOutput == text


    def test_code_1(self):
        from gdesk import gui
        import numpy as np
        import scipy.misc        
        
        arr = scipy.misc.face()
        gui.show(arr)
        gui.img.zoom_fit()
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Flip Horizontal'])
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Flip Vertical'])
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Canvas', 'Rotate 180'])
        
        assert (arr == gui.vs).all()
        
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Image', 'to Monochroom'])
        gui.img.cmap('turbo')


    def test_code_2(self):
        from gdesk import gui
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


    def test_colors(self):    
        from gdesk import gui
        from pylab import plt
        
        gui.clc()
        plt.close('all')
        gui.load_layout('console')
        
        banner = r" _____                                      ______             _    " + "\n" \
                 r"|  __ \                                     |  _  \           | |   " + "\n" \
                 r"| |  \/  __ _  _ __ ___   _ __ ___    __ _  | | | |  ___  ___ | | __" + "\n" \
                 r"| | __  / _` || '_ ` _ \ | '_ ` _ \  / _` | | | | | / _ \/ __|| |/ /" + "\n" \
                 r"| |_\ \| (_| || | | | | || | | | | || (_| | | |/ / |  __/\__ \|   < " + "\n" \
                 r" \____/ \__,_||_| |_| |_||_| |_| |_| \__,_| |___/   \___||___/|_|\_" + "\\"

        fgs = [227, 227, 222, 217, 212, 207]
        for fg, line in zip(fgs, banner.splitlines()):
            bg = 236
            pline = '\033[1m\033[48;5;{0:03d}m\033[38;5;{1:03d}m'.format(bg, fg) + line + '\033[0m'
            print(pline)
            
        answer = gui.question('Does GammaDesk look nice in the console output?')
        assert answer


def suite():
    suite = unittest.TestSuite()
    suite.addTest(GammaDeskSuite('test_screenstate_1'))
    suite.addTest(GammaDeskSuite('test_small_loop_and_print'))
    suite.addTest(GammaDeskSuite('test_colors'))
    suite.addTest(GammaDeskSuite('test_code_1'))
    suite.addTest(GammaDeskSuite('test_code_2'))    
    return suite

