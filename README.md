# htsget server

This is a reference implementation of a BAM/CRAM/VCF/BCF file server using [hstget protocol v1.1](https://github.com/samtools/hts-specs/blob/master/htsget.md).

The server can be run via the command line or programmatically.

Currently, this is a minimum-viable implementation, i.e. it implements all the unconditional MUST features from the spec, but only a subset of the optional features, hence the 0.x version. The goal is for v1.1 of this server to fully implement the spec, and for the features and version number to track that of the spec.

# Prerequisites

* Python 2.7 or 3.x

# Installation

The only dependency is `six` (for python 2/3 compatibility), which is installed automatically.

```bash
pip install htsget-server
```

# Command line interface

Run the server using default settings. It will serve files from the current working directory until killed by Ctrl-C.

```bash
htsget-server
```

Configure the port and file directory:

```bash
htsget-server -p 1234 -d /home/www/bams
```

# Programatic interface

```python
from python import htsgetserver

htsgetserver.run(port=1234, root='/home/www/bams')
```

# License

MIT

# Roadmap

The current features are not yet implemented. We are grateful for any contributions. Please see our [Code of Conduct]() and [Open Issues]().

* CRAM format
* BCF format
* HTTPS
* HTTP/2?
* RFC 2616 transfer-coding compression
* Retry logic for 5XX errors
* Authentication and authorization (OAuth 2.0)
* Fields filtering
* tags/notags
* MD5 checksum of response data
* Limit request retries
* Byte range http header
* Comma-delimited list of format preferences

# Out of scope/will not implement

* Discovery
* Inline data block URIs

# See also

* Consider using https://github.com/kennethreitz/responder
