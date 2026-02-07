import os
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

from interfaces.text import chat

if __name__ == "__main__":
    chat()
