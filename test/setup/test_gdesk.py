from gdesk import gui, config, __version__

gui.qapp.panels.ezm.set_perspective(config['layout']['image, levels & console'])

panid = 1
panel = gui.qapp.panels['console'][panid]
panel.stdio.stdOutputPanel.addText('This is the start-up banner, before thread is started\n')

test_code_1 = '''\
import unittest
import gdesk.test as test
runner = unittest.TextTestRunner()
runner.run(test.suite())        
'''

gui.console.execute_code(test_code_1, panid)
