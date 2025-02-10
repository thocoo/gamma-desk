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
        import time
        import sys
        from gdesk import gui

        gui.clc()

        expectedOutput = ''

        for i in range(42):
            line = f'i = {i}'
            print(line)
            expectedOutput += f'{line}\n'
            time.sleep(0.01)

        sys.stdout.flush()
        text = gui.console.text()
        assert expectedOutput == text, f"'{text}' != '{expectedOutput}'"


    def test_menu_file(self):
        from gdesk import gui

        gui.load_layout('image, levels & console')
        gui.img.select(1)

        gui.img.menu(['File', 'New...'], 1920, 1080, 4, 'uint8', 127)

        self.assertEqual(gui.vs.shape[0], 1080)
        self.assertEqual(gui.vs.shape[1], 1920)
        self.assertEqual(gui.vs.shape[2], 4)
        self.assertEqual(gui.vs.dtype, 'uint8')
        self.assertEqual(gui.vs.min(), 127)
        self.assertEqual(gui.vs.max(), 127)

        gui.img.menu(['File', 'New...'], 3840, 2160, 1, 'uint16', 2**16-1)

        self.assertEqual(gui.vs.shape[0], 2160)
        self.assertEqual(gui.vs.shape[1], 3840)
        self.assertEqual(len(gui.vs.shape), 2)
        self.assertEqual(gui.vs.dtype, 'uint16')
        self.assertEqual(gui.vs.min(), 2**16-1)
        self.assertEqual(gui.vs.max(), 2**16-1)

        gui.img.menu(['File', 'New...'], 640, 480, 3, 'double', 0.5)

        self.assertEqual(gui.vs.shape[0], 480)
        self.assertEqual(gui.vs.shape[1], 640)
        self.assertEqual(gui.vs.shape[2], 3)
        self.assertEqual(gui.vs.dtype, 'double')
        self.assertEqual(gui.vs.min(), 0.5)
        self.assertEqual(gui.vs.max(), 0.5)

        #https://imageio.readthedocs.io/en/stable/standardimages.html
        gui.img.menu(['File', 'Open Image...'], 'imageio:astronaut.png')
        gui.img.menu(['File', 'Open Image...'], 'imageio:wood.jpg')
        gui.img.menu(['File', 'Open Image...'], 'imageio:camera.png')

        gui.img.cmap('turbo')


    def test_menu_canvas(self):
        from gdesk import gui
        import scipy.misc

        arr = scipy.misc.face()
        height, width = arr.shape[:2]

        gui.load_layout('image, levels & console')
        gui.img.select(1)
        gui.show(arr)
        gui.img.zoom_fit()
        gui.menu_trigger('image', None, ['Canvas', 'Flip Horizontal'])
        gui.menu_trigger('image', None, ['Canvas', 'Flip Vertical'])
        gui.menu_trigger('image', None, ['Canvas', 'Rotate Left 90'])
        gui.menu_trigger('image', None, ['Canvas', 'Rotate Right 90'])
        gui.menu_trigger('image', None, ['Canvas', 'Rotate 180'])

        gui.menu_trigger('image', None, ['Canvas', 'Resize Canvas...'], width+64, height+32)
        gui.menu_trigger('image', None, ['Canvas', 'Resize Canvas...'], width, height)

        assert (arr == gui.vs).all()


    def test_menu_view(self):
        gui.load_layout('image, levels & console')
        gui.img.select(1)

        gui.img.menu(['File', 'Open Image...'], 'imageio:camera.png')

        gui.img.menu(['View', 'Refresh'])
        gui.img.menu(['View', 'Zoom In'])
        gui.img.menu(['View', 'Zoom Out'])
        gui.img.menu(['View', 'Zoom', 'Zoom 100%'])
        gui.img.menu(['View', 'Zoom', 'Zoom Fit'])
        gui.img.menu(['View', 'Zoom', 'Zoom Full'])
        gui.img.menu(['View', 'Zoom', 'Zoom Auto'])
        gui.img.menu(['View', 'Zoom', 'Zoom Exact...'], 50)

        gui.img.menu(['View', 'Default Offset & Gain'])
        gui.img.menu(['View', 'Set Current as Default'])
        gui.img.menu(['View', 'Offset & Gain...'], 0, 1, 2, 'grey')
        gui.img.menu(['View', 'Black & White...'], 10, 245, 'turbo')
        gui.img.menu(['View', 'Grey & Gain...'], 127, 4, 'jet')
        gui.img.menu(['View', 'Gain to Min-Max'])
        gui.img.menu(['View', 'Gain to Sigma', 'Gain to Sigma 1'])
        gui.img.menu(['View', 'Gain to Sigma', 'Gain to Sigma 2'])
        gui.img.menu(['View', 'Gain to Sigma', 'Gain to Sigma 3'])
        
        gui.img.menu(['View', 'HQ Zoom Out'])
        gui.img.menu(['View', 'Bind', 'Bind All Image Viewers'])
        gui.img.menu(['View', 'Bind', 'Unbind All Image Viewers'])
        gui.img.menu(['View', 'Bind', 'Absolute Zoom Link'])
        gui.img.menu(['View', 'Colormap...'], 'grey')
        gui.img.menu(['View', 'Colormap...'], 'clip')
        gui.img.menu(['View', 'Colormap...'], 'turbo')
        gui.img.menu(['View', 'Colormap...'], 'jet')
        gui.img.menu(['View', 'Colormap...'], 'invert')
        gui.img.menu(['View', 'Colormap...'], 'hot')
        gui.img.menu(['View', 'Colormap...'], 'cold')
        gui.img.menu(['View', 'Colormap...'], 'viridis')

        gui.img.menu(['View', 'Background Color...'], 58, 110, 165)
        gui.img.menu(['View', 'Selection Color...'], 255, 0, 0)
        gui.img.menu(['View', 'Value Format', 'Decimal'])
        gui.img.menu(['View', 'Value Format', 'Hex'])
        gui.img.menu(['View', 'Value Format', 'Binary'])
        gui.img.menu(['View', 'Show/Hide Profiles'])


    def test_menu_image_1(self):
        from gdesk import gui
        import imageio

        arr = imageio.imread('imageio:astronaut.png')

        gui.load_layout('image, levels & console')
        gui.img.select(1)
        imgpanid = gui.show(arr)
        gui.img.zoom_full()
        gui.menu_trigger('image', imgpanid, ['Image', 'Invert'])
        gui.menu_trigger('image', imgpanid, ['Image', 'Swap RGB | BGR'])
        gui.menu_trigger('image', imgpanid, ['Image', 'Adjust Lighting...'], 255, -1)
        gui.menu_trigger('image', imgpanid, ['Image', 'Swap RGB | BGR'])

        assert (arr == gui.vs).all()


    def test_menu_image_2(self):
        from gdesk import gui
        import imageio

        arr = imageio.imread('imageio:astronaut.png')

        gui.load_layout('image, levels & console')
        gui.img.select(1)
        gui.show(arr)

        gui.menu_trigger('image', None, ['Image', 'to Monochrome'])
        gui.menu_trigger('image', None, ['Edit', 'Show Prior Image'])
        gui.menu_trigger('image', None, ['Image', 'to Photometric Monochrome'])
        gui.menu_trigger('image', None, ['Edit', 'Show Prior Image'])

        assert (arr == gui.vs).all()


    def test_code_3(self):
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

        answer = gui.question('Looks everything OK?')

        plt.close('all')
        gui.menu_trigger('image', GammaDeskSuite.panid, ['Edit', 'Show Prior Image'])


    def test_colors(self):
        import sys
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


    def test_calc_pi_break(self):
        """Calculate pi digits and break after a few seconds"""
        import sys
        import time
        import threading
        from gdesk import shell, gui

        interpreter = shell.this_interpreter()
        ptid = threading.get_ident()
        panid = gui.console.selected()

        def delayedBreak():
            time.sleep(1)
            gui.redirects[threading.get_ident()] = ptid
            gui.menu_trigger('console', panid, ['Execution', 'Async Break'])

        threading.Thread(target=delayedBreak).start()

        def calcPi():
            q, r, t, k, n, l = 1, 0, 1, 1, 3, 3
            while True:
                if 4*q+r-t < n*t:
                    yield n
                    nr = 10*(r-n*t)
                    n  = ((10*(3*q+r))//t)-10*n
                    q  *= 10
                    r  = nr
                else:
                    nr = (2*q+r)*l
                    nn = (q*(7*k)+2+(r*l))//(t*l)
                    q  *= k
                    t  *= l
                    l  += 2
                    k += 1
                    n  = nn
                    r  = nr

        pi_digits = calcPi()
        i = 0

        print(f"{i:05d} ", end='')

        try:
            for d in pi_digits:
                sys.stdout.write(str(d))
                i += 1
                if (i % 64) == 0: print(f"\n{i:05d} ", end='')

        except KeyboardInterrupt:
            interpreter.break_sent = False


def suite():
    suite = unittest.TestSuite()
    suite.addTest(GammaDeskSuite('test_screenstate_1'))
    suite.addTest(GammaDeskSuite('test_small_loop_and_print'))
    suite.addTest(GammaDeskSuite('test_calc_pi_break'))
    suite.addTest(GammaDeskSuite('test_colors'))
    suite.addTest(GammaDeskSuite('test_menu_file'))
    suite.addTest(GammaDeskSuite('test_menu_canvas'))
    suite.addTest(GammaDeskSuite('test_menu_image_1'))
    suite.addTest(GammaDeskSuite('test_menu_image_2'))
    suite.addTest(GammaDeskSuite('test_code_3'))
    return suite

