import os
import uvicorn
if __name__ == '__main__':
    uvicorn.run('app.main:app', host=os.environ.get('BIBLE_HOST', '127.0.0.1'), port=int(os.environ.get('BIBLE_PORT', '8765')), access_log=False)
