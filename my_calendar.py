import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from main_window import CalendarWindow


def ensure_single_instance():
    """确保单实例运行。返回 (是否首个实例, QLocalServer 或 None)。"""
    socket = QLocalSocket()
    socket.connectToServer("CalendarDesk")
    if socket.waitForConnected(300):
        # 已有实例在运行，发送唤醒信号
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return False, None
    # 无已有实例，创建服务器监听
    QLocalServer.removeServer("CalendarDesk")
    server = QLocalServer()
    if server.listen("CalendarDesk"):
        return True, server
    return True, None  # 监听失败也作为首个实例继续（降级）


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    is_first, single_server = ensure_single_instance()
    if not is_first:
        sys.exit(0)
    win = CalendarWindow()
    if single_server:
        win._single_server = single_server
        single_server.newConnection.connect(win.handle_new_connection)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
