from argparse import ArgumentParser, ArgumentError
from pathlib import Path
import htsgetserver
import os


def directory(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise ArgumentError(f"Directory does not exist: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise ArgumentError(f"Insufficient permissions to read from directory {path}")
    return path


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-d",
        "--root-directory",
        type=directory,
        default=os.getcwd(),
        help="Directory from which to serve files. ({})".format(os.getcwd())
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=htsgetserver.DEFAULT_PORT,
        help="Port on which the server will listen. ({})".format(
            htsgetserver.DEFAULT_PORT)
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=htsgetserver.DEFAULT_BLOCK_SIZE,
        help="Maximum size of file chunks to be served. ({})".format(
            htsgetserver.DEFAULT_BLOCK_SIZE)
    )
    args = parser.parse_args()
    htsgetserver.run(
        directory=args.root_directory,
        port=args.port,
        block_size=args.block_size
    )
