import os
import uvicorn
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()  # важно для Android при запуске дочерних процессов
    os.chdir(os.path.dirname(__file__))  # переходим в папку backend

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",   # <-- измени здесь
        port=8000,
        reload=False,
        workers=1
    )