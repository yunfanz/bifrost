
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

"""
A simple block that accepts 1 frame at a time and accumulates them
nframe times before outputting the accumulated result.
"""

from __future__ import absolute_import

import bifrost as bf
from bifrost.pipeline import TransformBlock

from copy import deepcopy

class AccumulateBlock(TransformBlock):
    """Accumulate and sum frames of a ring on the GPU.

    Use this block to reshape a data stream into larger chunks.

    Attributes
    ----------
    iring : :obj:`bifrost.ring.Ring`
        Input ring.
    nframe : int
        Number of frames to accumulate.
    dtype : :obj:`str`, optional
        Output datatype. If None (default),
        input datatype of `iring` is used.
    gulp_nframe : int, optional
        How many incoming frames to read at
        once.
    *args
        Arguments to `bifrost.pipeline.TransformBlock`.
    **kwargs
        Keyword Arguments to `bifrost.pipeline.TransformBlock`.
    """
    def __init__(self, iring, nframe, dtype=None, gulp_nframe=1,
                 *args, **kwargs):
            assert(gulp_nframe == 1)
            super(AccumulateBlock, self).__init__(iring, gulp_nframe=1,
                                                  *args, **kwargs)
            self.nframe = nframe
            self.dtype  = dtype
    def define_valid_input_spaces(self):
            """Return set of valid spaces (or 'any') for each input"""
            return ('cuda',)
    def on_sequence(self, iseq):
            ihdr = iseq.header
            itensor = ihdr['_tensor']
            ohdr = deepcopy(ihdr)
            otensor = ohdr['_tensor']
            if 'scales' in otensor:
                    frame_axis = otensor['shape'].index(-1)
                    otensor['scales'][frame_axis][1] *= self.nframe
            if self.dtype is not None:
                    otensor['dtype'] = self.dtype
            self.frame_count = 0
            return ohdr
    def on_data(self, ispan, ospan):
            idata = ispan.data
            odata = ospan.data
            beta = 0. if self.frame_count == 0 else 1.
            bf.map("b = beta * b + (b_type)a", a=idata, b=odata, beta=beta)
            self.frame_count += 1
            if self.frame_count == self.nframe:
                    ncommit = 1
                    self.frame_count = 0
            else:
                    ncommit = 0
            return ncommit

def accumulate(iring, nframe, dtype=None, gulp_nframe=1,
        *args, **kwargs):
    """Accumulate frames of a ring.

    This is the handler for `AccumulateBlock`

    Attributes
    ----------
    iring : :obj:`bifrost.ring.Ring`
        Input ring.
    nframe : int
        Number of frames to accumulate.
    dtype : :obj:`str`, optional
        Output datatype. If None (default),
        input datatype of `iring` is used.
    gulp_nframe : int, optional
        How many incoming frames to read at
        once.
    *args
        Arguments to `bifrost.pipeline.TransformBlock`.
    **kwargs
        Keyword Arguments to `bifrost.pipeline.TransformBlock`.
    """
    return AccumulateBlock(iring, nframe, *args, **kwargs)
