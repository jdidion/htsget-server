import errno
import logging
import os
import signal
from typing import Tuple, Dict, Callable, Type, Any, Optional

from ngsindex import parse_index
from ngsindex.utils import BinReader

from htsgetserver.store import Resource


class Runnable:
    def run(self, **kwargs):
        pass

    def stop(self):
        pass


def run_interruptible(
    runnable: Runnable, error_handlers: Dict[Type[Exception], Tuple[str, int]] = None,
    signal_callbacks: Dict[int, Callable[[int, Any], None]] = None,
    error_on_interrupt: bool = False, **kwargs
):
    """Run a function, gracefully handling keyboard interrupts.

    Args:
        runnable: A Runnable instance.
        error_handlers: Additional specific exception types to handle. Dict
            mapping exception type to tuple of (message, return code).
        signal_callbacks: Dict mapping signal IDs to callables. Callables take
            two parameters: signal, stack frame. Callbacks are registered before
            running func and unregistered after. By default, SIGQUIT is handled
            by generating a core dump (granted that core dumps have been enabled
            at the OS level).
        error_on_interrupt: Whether to exit with a non-zero return code when the
            program is terminated by a keyboard interrupt.
        kwargs: Keyword arguments to pass to `func`.

    Returns:
        A (unix-style) return code (0=normal, anything else is an error).
    """
    log = logging.getLogger()

    if signal_callbacks is None:
        signal_callbacks = {}

    if signal.SIGQUIT not in signal_callbacks:
        def core_dump_on_quit(_sig, frame):
            log.error("Received signal %s; aborting", _sig)
            log.error("Stack frame: %s", frame)
            os.abort()

        signal_callbacks[signal.SIGQUIT] = core_dump_on_quit

    for sig, callback in signal_callbacks.items():
        signal.signal(sig, callback)

    err_types = tuple(error_handlers.keys()) if error_handlers else ()
    retcode = 0

    try:
        runnable.run(**kwargs)
    except KeyboardInterrupt:
        if error_on_interrupt:
            log.error("Interrupted")
            retcode = 130
        else:
            log.info("Interrupted")
    except IOError as err:
        if err.errno == errno.EPIPE:
            log.error("Broken pipe", exc_info=True)
        else:
            log.error("IO error", exc_info=True)
        retcode = 1
    except err_types as err:
        msg, retcode = error_handlers[type(err)]
        log.error(msg, exc_info=True)
    except:
        log.error("Unknown error", exc_info=True)
        retcode = 1
    finally:
        runnable.stop()

    for sig in signal_callbacks.keys():
        signal.signal(sig, signal.SIG_DFL)

    return retcode


# NOTE: For BCF files, an index file will be required, as the first body record is not
# de facto guaranteed to be at the start of a bgzf block the way it is for BAM.


def get_bam_header_size(
    bam_resource: Resource, index_resource: Optional[Resource] = None
) -> int:
    """Determines the size of the file's header.

    If B is the size of the header and N is the size of the file, splitting the file
    into two pieces f1=file[0:B] and f2=file[b:N] will result in f1 being a file that
    can be parsed by htslib (after appending the 28 byte EOF marker, see section 4.1.2
    of the SAM spec http://samtools.github.io/hts-specs/SAMv1.pdf).

    There are two different ways to determine the header size. If the index file is
    available, we parse the index using ngsindex and then find the smallest offset
    in the linear index. Otherwise, we read the header of the uncompressed BAM file,
    sum up the uncompressed size of the header, then read the bgzip blocks of the
    compressed BAM file to find the size of all the blocks used to store the header.

    Thanks to John Marshall for describing this solution:
    https://github.com/samtools/hts-specs/pull/325#issuecomment-405746930

    Returns:
        The size of the file's header in bytes.
    """
    if index_resource is None:
        # First find the uncompressed size of the header
        with bam_resource.open("b", decompress=True) as bam_file:
            uncompressed_size = 12
            reader = BinReader(fileobj=bam_file, byte_order="<")
            reader.read_string(3, True)  # magic string
            reader.read_byte()  # version
            l_text = reader.read_int()  # length of header text
            uncompressed_size += l_text
            reader.read_string(l_text, True)  # header text
            n_ref = reader.read_int()
            for _ in range(n_ref):
                l_name = reader.read_int()
                reader.read_string(l_name, True)
                reader.read_int()
                uncompressed_size += 8 + l_name

        # Now find the number of blocks used to store the header
        with bam_resource.open("b", decompress=False) as bam_file:
            reader = BinReader(fileobj=bam_file, byte_order="<")
            header_size = 0
            block_size = 0
            while block_size < uncompressed_size:
                reader.read_ubytes(4)  # fixed-values
                reader.read_uint()  # MTIME
                reader.read_ubytes(2)  # XFL and OS
                xlen = reader.read_ushort()  # size of the extra subfields (should be 6)
                if xlen != 6:
                    raise ValueError("Extra RFC1952 subfields not yet supported")
                if reader.read_ubytes(2) != (66, 67):  # subfield IDs
                    raise ValueError("Invalid subfield identifier")
                if reader.read_ushort() != 2:  # SLEN
                    raise ValueError("Invalid subfield length")
                bsize = reader.ushort()  # total block size - 1
                header_size += bsize
                reader.read_ubytes(bsize - xlen - 19)  # CDATA
                reader.read_uint()  # CRC32
                block_size += reader.read_uint()  # ISIZE
            return header_size + 1
    else:
        with index_resource.open("b") as index_file:
            index = parse_index(fileobj=index_file)
            return min(
                offset.file_offset
                for ref_index in index.ref_indexes
                for offset in ref_index.intervals
            )
