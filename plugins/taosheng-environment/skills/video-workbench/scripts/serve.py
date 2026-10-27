"""临时预览包内视频看板；只监听回环地址，不安装、不更新任何内容。"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8878)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('请选择 1024–65535 的空闲端口')
    board = Path(__file__).resolve().parent.parent / 'assets' / 'board'
    if not (board / 'index.html').is_file():
        parser.error('缺少 assets/board/index.html，请使用完整发行包')
    # 本发行包不带符号链接，避免 HTTP 目录越出包内范围。
    if any(p.is_symlink() for p in board.rglob('*')):
        parser.error('看板目录含符号链接，拒绝服务目录外文件')
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(SimpleHTTPRequestHandler, directory=str(board)))
    except OSError as exc:
        parser.error(f'端口不可用：{exc}；请用 --port 选择另一端口')
    print(f'视频工作台：http://127.0.0.1:{args.port}/\n仅本机可访问，Ctrl-C 停止。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
