"""Private form storage: PostgreSQL in Render, SQLite for local use/tests."""
import os,sqlite3
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).parent
DATA=Path(os.environ.get('DATA_DIR',str(ROOT/'instance')));DATA.mkdir(parents=True,exist_ok=True)
DATABASE_URL=os.environ.get('DATABASE_URL','')
POSTGRES=bool(DATABASE_URL)

class PgConnection:
 def __init__(self,connection):self.connection=connection
 def execute(self,sql,params=()):return self.connection.execute(sql.replace('?','%s'),params)

@contextmanager
def db():
 if POSTGRES:
  import psycopg
  from psycopg.rows import dict_row
  connection=psycopg.connect(DATABASE_URL,row_factory=dict_row,connect_timeout=10)
  try:
   with connection:yield PgConnection(connection)
  finally:connection.close()
 else:
  connection=sqlite3.connect(DATA/'tecnoforms.db',timeout=15);connection.row_factory=sqlite3.Row
  try:
   with connection:yield connection
  finally:connection.close()

def initialize():
 ident='BIGSERIAL PRIMARY KEY' if POSTGRES else 'INTEGER PRIMARY KEY'
 binary='BYTEA' if POSTGRES else 'BLOB'
 with db() as c:
  c.execute(f'CREATE TABLE IF NOT EXISTS users(id {ident},email TEXT UNIQUE,name TEXT,password TEXT,logins INTEGER DEFAULT 0,onboarded INTEGER DEFAULT 0,profile TEXT)')
  c.execute(f'CREATE TABLE IF NOT EXISTS forms(id {ident},user_id BIGINT,title TEXT,fields TEXT,created TEXT)')
  extras={'status':"TEXT DEFAULT 'reviewed'",'batch_id':'TEXT','filename':'TEXT','image':binary,'error':'TEXT','updated':'TEXT'}
  if POSTGRES:
   for name,definition in extras.items():c.execute(f'ALTER TABLE forms ADD COLUMN IF NOT EXISTS {name} {definition}')
  else:
   columns={r['name'] for r in c.execute('PRAGMA table_info(forms)')}
   for name,definition in extras.items():
    if name not in columns:c.execute(f'ALTER TABLE forms ADD COLUMN {name} {definition}')
  c.execute('CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,user_id BIGINT,title TEXT,status TEXT,created TEXT,updated TEXT,message TEXT)')
  c.execute('CREATE INDEX IF NOT EXISTS forms_owner_batch ON forms(user_id,batch_id)')
  c.execute('CREATE INDEX IF NOT EXISTS batches_owner ON batches(user_id)')

def storage_info():return {'kind':'postgresql' if POSTGRES else 'sqlite','account_persistent':POSTGRES,'notice':os.environ.get('STORAGE_NOTICE','El historial local SQLite puede perderse si el servidor se reinicia. Descarga un respaldo.' if not POSTGRES else 'Historial guardado en PostgreSQL. Descarga respaldos periódicamente.')}
