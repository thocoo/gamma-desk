import sys
import sqlite3
import time
import shutil
import logging
from pathlib import Path

if sys.platform == 'win32':
    import msvcrt
    locking = msvcrt.locking
    LK_RLCK = msvcrt.LK_RLCK
    LK_UNLCK = msvcrt.LK_UNLCK
    
else:
    locking = lambda x, y, z: None
    LK_RLCK = None
    LK_UNLCK = None

from .conf import config

logger = logging.getLogger()

class LogDir(object):

    def __init__(self, rootpath):
        self.rootpath = Path(rootpath).expanduser()
        if not self.rootpath.exists():
            print(f"Creating log dir: {self.rootpath}")
            self.rootpath.mkdir(parents=True)

    def make_lock_file(self, lock_file):
        """
        Make a empty lock file in the logpath.

        A windows readlock is attached to the file.
        The lock will be removed by windows if the process dies.
        When booting another instance of GDesk, this lock file will
        be used (the possibility to removed it) to detect if the
        logpath is currently in use by another GDesk process.
        """
        self.lock_file = lock_file
        self.lock_file.touch()
        self.lock_file_ptr = open(str(self.lock_file), 'r')
        locking(self.lock_file_ptr.fileno(), LK_RLCK, 1024)
        
    def release_lock_file(self):
        """
        Release and remove the current lock file.

        When this process dies, the lock is removed by windows but the
        file is not removed.
        """    
        locking(self.lock_file_ptr.fileno(), LK_UNLCK, 1024)
        self.lock_file_ptr.close()
        self.lock_file.unlink()
        
    def get_active_lock_files(self):
        active_locks = []
        for p in self.rootpath.glob('log.*'):
           if (p / 'cmdlog.lock').exists():
              try:
                  (p / 'cmdlog.lock').unlink()
              except PermissionError:
                  active_locks.append(p / 'cmdlog.lock')
        return active_locks
        
    def remove_inactive_log_dirs(self):
        active_locks = self.get_active_lock_files()
        for p in self.rootpath.glob('log.*'):
            if not (p / 'cmdlog.lock') in active_locks:
                shutil.rmtree(str(p))
            
    def find_log_path(self):
        """
        Find a suitable rootpath/log.N path.

        Which logpath contains an active lock file?
        Create a new log.N if needed.
        """
        priorlogpath = None
        for n in range(config['max_log_paths']):
            logpath_propose = self.rootpath / ('log.%d' % n)
            if logpath_propose.exists():
                # Is the path in use by other process?
                if not (logpath_propose / 'cmdlog.lock').exists():
                    logpath = logpath_propose
                    break
                else:
                    try:
                        (logpath_propose / 'cmdlog.lock').unlink()
                        # succesfull delete of lock file
                        # no process was using it
                        logpath = logpath_propose
                        break
                    except:
                        # Logs from this logpath should be copied to own logs.
                        priorlogpath = logpath_propose
            else:
                logpath_propose.mkdir()
                logpath = logpath_propose
                break
                
        else:
            print(f'Maximum number of {config["max_log_paths"]} log dirs reached')
            print(f'Please, remove deprecated dirs')
            print(f'{self.rootpath }')
            raise SystemExit()
                
        self.make_lock_file(logpath / 'cmdlog.lock')        
        self.logpath = logpath
        self.priorlogpath = priorlogpath
                
        return logpath, priorlogpath

class History(object):
    def __init__(self, logdir):
        self.init_server(logdir)
        
    def init_server(self, logdir=None):
        if logdir is None:
            self.server_file = None
            self.server = sqlite3.connect(':memory:')            
            self.define_tables()
        else:
            logdir = Path(logdir)
            if not logdir.exists():
                logdir.mkdir(parents=True)                
            logdir = logdir.absolute()
            self.server_file = logdir / 'ghhist.db'
            #Python 3.6 doesn't understand Path
            self.server = sqlite3.connect(str(self.server_file))
            self.define_tables()
            
    def import_command_history(self, other_logfile):  
        self.server.execute('ATTACH [%s] as OTHERDB' % str(other_logfile))
        q = 'INSERT INTO CMDHIST (TIME, CMD) SELECT TIME, CMD FROM [OTHERDB].[CMDHIST]'
        self.server.execute(q)
        self.server.commit()
        self.server.execute('DETACH OTHERDB')            
            
    def define_tables(self):
        query = """CREATE TABLE IF NOT EXISTS CMDHIST (
ID INTEGER PRIMARY KEY, TIME TEXT, CMD TEXT)"""
        self.server.execute(query)
        
        query = """CREATE TABLE IF NOT EXISTS PATHHIST (
ID INTEGER PRIMARY KEY, CATEGORY TEXT, TIME TEXT, PATH TEXT)"""
        self.server.execute(query)
        
        query = """ALTER TABLE PATHHIST ADD COLUMN CATEGORY TEXT"""
        try:
            self.server.execute(query)
        except:
            pass        
            
    def execfetch(self, query, parameters=()):        
        cur = self.server.cursor()
        cur.execute(query, parameters)
        row = cur.fetchone()
        while row !=  None:
            yield row
            row = cur.fetchone()        

    def logcmd(self, cmd):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        query = "INSERT INTO CMDHIST (TIME, CMD) VALUES (?, ?)"
        self.server.execute(query, (now, cmd,))
        self.server.commit()
        self.skip = -1
        rowid = None
        for col in self.execfetch("SELECT last_insert_rowid()"):
            rowid = col[0]
        return rowid
         
    def storepath(self, path, delete_old_entry=True, category='image'):
        if delete_old_entry:
            self.server.execute("DELETE FROM PATHHIST WHERE PATH = ?", (path,))        
            
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        query = "INSERT INTO PATHHIST (CATEGORY, TIME, PATH) VALUES (?, ?, ?)\n"
        self.server.execute(query, (category, now, path,))
        self.server.commit()

        rowid = None
        for col in self.execfetch("SELECT last_insert_rowid()"):
            rowid = col[0]
        return rowid      

    def yield_recent_paths(self, count=20, category='image'):        
        for row in self.execfetch("SELECT ID, TIME, PATH FROM PATHHIST WHERE CATEGORY = ? ORDER BY ID DESC LIMIT ?", (category, count)):
            yield row
            
        
    def retrievecmd(self, part='', from_id=None, distinct=True, back=True, prefix=True):        
            
        query = self.make_retrieve_query(1, part, from_id, distinct, back, prefix)
        
        for cmdid, cmd in self.execfetch(query):
            return cmdid, cmd
            
        return from_id, part

    def tail(self, count=20, part='', from_id=None, distinct=False, back=True, prefix=True, reverse=True):
        cmds = []
        
        query = self.make_retrieve_query(count, part, from_id, distinct, back, prefix)
            
        for row in self.execfetch(query):
            cmds.append(row)
            
        if reverse:
            return cmds[::-1]
        else:
            return cmds
            
    def make_retrieve_query(self, count=20, part='', from_id=None, distinct=False, back=True, prefix=True):
    
        if back:
            order = 'DESC'
            if not (from_id is None or from_id == 0):
                rng = f" WHERE ID < {from_id}"
            else:
                rng = ''
        else:
            order = 'ASC'
            if not (from_id is None or from_id == 0):
                rng = f" WHERE ID > {from_id}"            
            else:
                rng = ''
                
        if prefix:
            wild = ''
        else:
            wild = '%'
            
        part = part.replace("'","''")
            
        if distinct:
            query = f"SELECT LASTID AS ID, CMD FROM (SELECT MAX(ID) AS LASTID, CMD FROM CMDHIST WHERE CMD LIKE '{wild}{part}%' GROUP BY CMD ORDER BY LASTID {order}){rng} LIMIT {count}"
        else:
            query = f"SELECT ID, CMD FROM (SELECT ID, CMD FROM CMDHIST WHERE CMD LIKE '{part}%'{rng} ORDER BY ID {order}){rng} LIMIT {count}"

        return query
        
    def delete_all_but_last(self, keep_count=100):
        count = next(self.execfetch('SELECT COUNT(*) FROM CMDHIST'))[0]
        keep_count = min(count, keep_count)
        keep_id = next(self.execfetch(f'SELECT ID FROM CMDHIST ORDER BY ID DESC LIMIT {keep_count}, 1'))[0]
        self.server.execute(f'DELETE FROM CMDHIST WHERE ID < {keep_id}')
        self.server.execute('COMMIT')
        self.server.execute('REINDEX CMDHIST')
        self.server.execute('VACUUM')
            
