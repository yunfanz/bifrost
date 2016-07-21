
# Copyright (c) 2016, The Bifrost Authors. All rights reserved.
# Copyright (c) 2016, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of The Bifrost Authors nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This file provides a direct interface to libbifrost.so

# PYCLIBRARY ISSUE: Passing the wrong handle type to a function gives this meaningless error:
#  ArgumentError: argument 1: <type 'exceptions.TypeError'>: expected LP_s instance instead of LP_s
#  E.g., _bf.RingSequenceGetName(<BFspan>) [should be <BFsequence>]

def _load_bifrost_lib():
	import os
	# TODO: Keep these up-to-date
	headers = ["common.h", "affinity.h", "memory.h",
	    "ring.h", "transpose.h", "fft.h"]
	library_name = "libbifrost.so"
	api_prefix   = "bf"
	header_paths = ["/usr/local/include/bifrost",
					"../src/bifrost"] # TODO: Remove this one?
	include_env  = 'BIFROST_INCLUDE_PATH'
	# PYCLIBRARY ISSUE
	# TODO: Would it make sense to build this into PyCLibrary?
	library_env  = 'LD_LIBRARY_PATH'
	home_dir     = os.path.expanduser("~")
	parser_cache = os.path.join(home_dir, ".cache/bifrost.parse")
	
	def _get_env_paths(env):
		paths = os.getenv(env)
		if paths is None:
			return []
		return [p for p in paths.split(':')
				if len(p.strip())]
		
	import pyclibrary
	from pyclibrary import CParser, CLibrary
	
	import ctypes
	# PYCLIBRARY ISSUE Should these be built in? Optional extra?
	# Note: This is needed because pyclibrary starts with only
	#         the fundamental types (short, int, float etc.).
	#extra_types = {}
	#extra_types = {'uint64_t': ctypes.c_uint64}
	extra_types = {
		' uint8_t': ctypes.c_uint8,
		'  int8_t': ctypes.c_int8,
		'uint16_t': ctypes.c_uint16,
		' int16_t': ctypes.c_int16,
		'uint32_t': ctypes.c_uint32,
		' int32_t': ctypes.c_int32,
		'uint64_t': ctypes.c_uint64,
		' int64_t': ctypes.c_int64
	}
	
	try:
		pyclibrary.auto_init(extra_types=extra_types)
	except RuntimeError:
		pass # WAR for annoying "Can only initialise the parser once"
	header_paths += _get_env_paths(include_env)
	valid_header_paths = [p for p in header_paths if os.path.exists(p)]
	pyclibrary.utils.add_header_locations(valid_header_paths)
	try:
		_parser = CParser(headers, cache=unicode(parser_cache, "utf-8"))
	except AttributeError: # # PYCLIBRARY ISSUE WAR for "'tuple' has no attribute 'endswith'" bug
		raise ValueError("Could not find Bifrost headers.\nSearch paths: "+
						 str(header_paths))
	pyclibrary.utils.add_library_locations(_get_env_paths(library_env))
	lib = CLibrary(library_name, _parser, prefix=api_prefix)
	return lib

_bf = _load_bifrost_lib() # Internal access to library
bf = _bf                  # External access to library

# Internal helper functions below

def _array(typ, size_or_vals):
	from pyclibrary import build_array
	try:
		_ = iter(size_or_vals)
		vals = size_or_vals
		return build_array(_bf, typ, size=len(vals), vals=vals)
	except TypeError:
		size = size_or_vals
		return build_array(_bf, typ, size=size)

def _check(f):
	status, args = f
	if status != _bf.BF_STATUS_SUCCESS:
		if status is None:
			raise RuntimeError("WTF, status is None")
		if status == _bf.BF_STATUS_END_OF_DATA:
			raise StopIteration()
		else:
			status_str, _ = _bf.GetStatusString(status)
			raise RuntimeError(status_str)
	return f

def _get(f, retarg=-1):
	status, args = _check(f)
	return list(args)[retarg]

def _retval(f):
	ret, args = f
	return ret

def _string2space(s):
	lut = {'auto':         _bf.BF_SPACE_AUTO,
	       'system':       _bf.BF_SPACE_SYSTEM,
	       'cuda':         _bf.BF_SPACE_CUDA,
	       'cuda_host':    _bf.BF_SPACE_CUDA_HOST,
	       'cuda_managed': _bf.BF_SPACE_CUDA_MANAGED}
	if s not in lut:
		raise KeyError("Invalid space '"+str(s)+"'.\nValid spaces: "+str(lut.keys()))
	return lut[s]
def _space2string(i):
	return {_bf.BF_SPACE_AUTO:         'auto',
	        _bf.BF_SPACE_SYSTEM:       'system',
	        _bf.BF_SPACE_CUDA:         'cuda',
	        _bf.BF_SPACE_CUDA_HOST:    'cuda_host',
	        _bf.BF_SPACE_CUDA_MANAGED: 'cuda_managed'}[i]


# DuCT library load.
# Split this library load into another file

# Config: The shared library comes from DuCT (https://bitbucket.org/hughbg/duct).
# The library is libduct.so.1 which needs to be in /usr/local/lib and a link set
# to it called libduct.so. The header file duct_light.h needs to be in /usr/local/include.

def _load_duct_lib():
        import os
        # TODO: Keep these up-to-date
        headers = ["duct_light.h"]
        libraries = [ "libstar.so", "libpal.so", "libduct.so" ]
        api_prefix   = "duct"
        header_paths = ["/usr/local/include/"]

        # PYCLIBRARY ISSUE
        # TODO: Would it make sense to build this into PyCLibrary?
        library_env  = 'LD_LIBRARY_PATH'
        home_dir     = os.path.expanduser("~")
        parser_cache = os.path.join(home_dir, ".cache/bifrost.parse")

        def _get_env_paths(env):
                paths = os.getenv(env)
                if paths is None:
                        return []
                return [p for p in paths.split(':')
                                if len(p.strip())]

        import pyclibrary
        from pyclibrary import CParser, CLibrary

        import ctypes
        # PYCLIBRARY ISSUE Should these be built in? Optional extra?
        # Note: This is needed because pyclibrary starts with only
        #         the fundamental types (short, int, float etc.).
        #extra_types = {}
        #extra_types = {'uint64_t': ctypes.c_uint64}
        extra_types = {
                ' uint8_t': ctypes.c_uint8,
                '  int8_t': ctypes.c_int8,
                'uint16_t': ctypes.c_uint16,
                ' int16_t': ctypes.c_int16,
                'uint32_t': ctypes.c_uint32,
                ' int32_t': ctypes.c_int32,
                'uint64_t': ctypes.c_uint64,
                ' int64_t': ctypes.c_int64
        }

        try:
                pyclibrary.auto_init(extra_types=extra_types)
        except RuntimeError:
                pass # WAR for annoying "Can only initialise the parser once"
        valid_header_paths = [p for p in header_paths if os.path.exists(p)]
        pyclibrary.utils.add_header_locations(valid_header_paths)
        try:
                _parser = CParser(headers, cache=unicode(parser_cache, "utf-8"))
        except AttributeError: # # PYCLIBRARY ISSUE WAR for "'tuple' has no attribute 'endswith'" bug
                raise ValueError("Could not find duct header.\nSearch paths: "+
                                                 str(header_paths))
        pyclibrary.utils.add_library_locations(_get_env_paths(library_env))
        lib = CLibrary("libduct.so", _parser, prefix=api_prefix)
        return lib

_duct = _load_duct_lib()    # Internal access to library
duct = _duct                # External access to library

# This is the only function to call. The argument is a DADA file name. File must
# be in time order format, not reg tile. The config files used by corr2uvfits must be
# in the current directory. They are antenna locations, cable lengths and connections,
# and header file with RA/DEC, DATE, TIME etc. Usually called antenna_locations.txt,
# instr_config.txt, header.txt. header.txt has to be regenerated for each DADA file.
# The output is a 2-D array that has been flattened to 1-D. The dimensions of the array
# in 2-D are [31626][6]. The first dimension is the baselines (minus the outrigger baselines).
# The second dimension accesses 6 numbers for a baseline: stand1, stand2, U, V, Visibility(Real),
# Visibility(Imag). 
# The library currently does not have proper error handling so there could be undetermined
# behaviour if there is an error.
def load_dada_visibilities(dada_file_name):
  ret = duct.load_dada_light(dada_file_name)
  return ret()

# Example
# x = load_dada_visibilities("/nfs/longterm1/ledaovro7/data1/one/2015-04-08-20_15_03_0001133593833216.dada")
# baseline = 1000
# print x[baseline*6+3]		# Prints V for baseline 1000. UV are in metres.

