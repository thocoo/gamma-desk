import logging

logger = logging.getLogger(__name__)

class LayoutStruct(object):
    def __init__(self):
        self.root = dict()
        # self.root['type'] = 'layout'
        # self.root['category'] = 'hbox'
        # self.root['items'] = []
        # self.root['sizes'] = []
        self.tabblock = True  #Don't split inside tabs, go back one level
        
    def insert_panel(self, panel, relation='right', to_panel=None, size=100):
        category, panid = panel       
        new_node = {'type': 'panel', 'category': category, 'id': panid}     
        self.insert_panel_tree(self.root, new_node, relation, to_panel, size)
        
    def insert_branch(self, branch, relation='right', to_panel=None, size=100):   
        self.insert_panel_tree(self.root, branch, relation, to_panel, size)        
        
    def is_empty(self):            
        def node_is_empty(node):
            if len(node.keys()) == 0:
                return True
                
            elif node['type'] == 'panel':
                return False
                    
            for node in node.get('items', []):
                if not node_is_empty(node):
                    return False
                    
            return True
                
        return node_is_empty(self.root)
        
    def pop_node(self, nodetype='layout', category='tab', node_id=None):                    
        
        def check_node(subnode):        
            if subnode['type'] == nodetype and \
                subnode['category'] == category and \
                subnode.get('id', None) == node_id:
                return True
            else:
                return False
            
        if check_node(self.root):            
            poped_node = self.root
            self.root = dict()
            # self.root['type'] = 'layout'
            # self.root['category'] = 'hbox'
            # self.root['items'] = []
            # self.root['sizes'] = []     

            l = LayoutStruct()  
            l.root = poped_node            
            return l
            
        if not 'items' in self.root.keys():
            return None           
    
        def pop_node_brach(node):
            #print(f'node: {node}')
            found_index = None
            poped_node = None
            for index, subnode in enumerate(node['items']):
                if check_node(subnode):
                    found_index = index
                    break
                    
                elif poped_node is None and subnode['type'] != 'panel':
                    poped_node = pop_node_brach(subnode)
                    
            if poped_node is None and not found_index is None:
                poped_node = node['items'].pop(found_index)
                if 'sizes' in node.keys():
                    pinned_size = len(node['sizes'])
                    if found_index < pinned_size:
                        #In the pinned area
                        node['sizes'].pop(found_index) 
                    else:
                        #In the scroll area
                        node['scroll'].pop(found_index-pinned_size)
                    
            #print(f'poped_node: {poped_node}')
            return poped_node
                    
        poped_root = pop_node_brach(self.root)
        l = LayoutStruct()
        l.root = poped_root
        return l

    def insert_panel_tree(self, node, new_node, relation, to_panel=None, size=100):
        """
        Relation is either: 'left', 'right', 'top', 'bottom' or 'tab'
        """       
        
        if not to_panel is None and not node['type'] == 'panel':
            top = False
            to_category, to_panid = to_panel                    
            item_index = None
            found_deeper = False
            for index, item in enumerate(node['items']):
                if item['type'] == 'panel':
                    if item['category'] == to_category and item['id'] == to_panid:
                        item_index = index
                else:
                    found_deeper = self.insert_panel_tree(item, new_node, relation, to_panel, size)
                    if found_deeper:
                        item_index = index
                    
        else:
            top = True
            if relation in ['left', 'top']:
                item_index = 0
                
            elif relation in ['right', 'bottom']:
                if node['type'] == 'panel':
                    #probably as top level single panel
                    item_index = -1
                else:
                    item_index = len(node['items']) - 1
                
            elif relation in ['tab']:
                item_index = -1 #Will not be used
        
        if not item_index is None:            
            if relation in ['left', 'right']:
                if not node['category'] == 'hbox':                    
                    if top:
                        #insert a hbox at top level
                        self.root = {'type': 'layout', 'category': 'hbox', 'items': [node], 'sizes': [size]}  
                        self.insert_panel_tree(self.root, new_node, relation, to_panel, size)
                    elif self.tabblock and node['category'] == 'tab':
                        #Go back one level
                        return True
                    else:
                        #insert a hbox at this level
                        subnode = node['items'][item_index]
                        node['items'][item_index] = {'type': 'layout', 'category': 'hbox', 'items': [subnode], 'sizes': [size]}                                             
                        self.insert_panel_tree(node['items'][item_index], new_node, relation, to_panel, size)
                    
                elif node['category'] == 'hbox':
                    #Add the item to the current hbox
                    if relation == 'left':
                        node['items'].insert(item_index, new_node)
                        node['sizes'].insert(item_index, size)
                        
                    elif relation == 'right':
                        if item_index == len(node['items']) - 1:                
                            node['items'].append(new_node)
                            node['sizes'].append(size)    
                        else:
                            node['items'].insert(item_index+1, new_node)
                            node['sizes'].insert(item_index+1, size)
                        
            elif relation in ['top', 'bottom']:
                if not node['category'] == 'vbox':
                    if top:
                        #insert a vbox at top level
                        self.root = {'type': 'layout', 'category': 'vbox', 'items': [node], 'sizes': [size]}  
                        self.insert_panel_tree(self.root, new_node, relation, to_panel, size)                    
                        
                    elif self.tabblock and node['category'] == 'tab':
                        #Go back one level
                        return True
                        
                    else:
                        #insert a vbox at this levels
                        subnode = node['items'][item_index]
                        node['items'][item_index] = {'type': 'layout', 'category': 'vbox', 'items': [subnode], 'sizes': [size]} 
                        self.insert_panel_tree(node['items'][item_index], new_node, relation, to_panel, size)
                    
                elif node['category'] == 'vbox':
                    #Add the item to the current hbox
                    if relation == 'top':
                        node['items'].insert(item_index, new_node)
                        node['sizes'].insert(item_index, size)        
                    elif relation == 'bottom':
                        if item_index == len(node['items']) - 1:                
                            node['items'].append(new_node)
                            node['sizes'].append(size)    
                        else:
                            node['items'].insert(item_index+1, new_node)
                            node['sizes'].insert(item_index+1, size)
                            
            elif relation in ['tab']:
                if not node['category'] == 'tab':
                    if top:
                        self.root = {'type': 'layout', 'category': 'tab', 'items': [node]}  
                        self.insert_panel_tree(self.root, new_node, relation, to_panel, size)                    
                    else:
                        subnode = node['items'][item_index]
                        node['items'][item_index] = {'type': 'layout', 'category': 'tab', 'items': [subnode]} 
                        self.insert_panel_tree(node['items'][item_index], new_node, relation, to_panel, size)
                else:
                    node['items'].append(new_node)             
    
    def compact(self):
        if not 'items' in self.root.keys():
            return
            
        self.compact_branch(self.root)
        
        if len(self.root['items']) == 0:
            self.root = dict()
            self.root['type'] = 'layout'
            self.root['category'] = 'hbox'
            self.root['items'] = []
            self.root['sizes'] = []
        
        elif len(self.root['items']) == 1:
            self.root = self.root['items'][0]                   
              
    def compact_branch(self, node):                
        zero_items = []
        
        for index, subnode in enumerate(node['items']):        
            if subnode['type'] == 'panel':
                continue
                
            self.compact_branch(subnode)
            
            if len(subnode['items']) == 0:
                zero_items.append(subnode)
                
            elif len(subnode['items']) == 1:
                node['items'][index] = subnode['items'][0]                
                
        for item in zero_items:
            node['items'].remove(item)          
            
    def distribute(self):    
        def distribute_branch(node):
            if node['type'] == 'panel':
                return
                
            if 'sizes' in node.keys():
                mean = sum(node['sizes']) / len(node['sizes'])
                node['sizes'] = len(node['sizes']) * [mean]

            for subnode in node['items']:
                distribute_branch(subnode)            
                
        distribute_branch(self.root)                
                
    def show(self):
        print(self.describe())

    def describe(self):
        if self.root.get('type', None) == None:
            return
            
        lines = LayoutStruct.show_branch(self.root)
        return '\n'.join(lines)
        
    @staticmethod
    def show_branch(node, prefix=''):
        lines = []
        
        if node['type'] == 'panel':
            lines.append(f"{prefix}{node['category']}#{node['id']}")
            
        elif node['category'] in ['tab', 'tag']:   
            tabid = node.get('id', None)
            active = node.get('active', '')
            lines.append(f"{prefix}{node['type']} {node['category']} {tabid} {active}")
            for subnode in node['items']:
                lines.extend(LayoutStruct.show_branch(subnode, prefix + '  '))

        else:
            tabid = node.get('id', None)
            lines.append(f"{prefix}{node['type']} {node['category']} {tabid} {node['sizes']}")
            for subnode in node['items']:
                lines.extend(LayoutStruct.show_branch(subnode, prefix + '  '))

        return lines  