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

import unittest
import bifrost
import json
import os
import numpy as np
from bifrost.block import WriteAsciiBlock, Pipeline, TestingBlock, NearestNeighborGriddingBlock
from bifrost.addon.leda.blocks import DadaReadBlock, NewDadaReadBlock

def load_telescope(filename):
    with open(filename, 'r') as telescope_file:
        telescope = json.load(telescope_file)
    coords_local = np.array(telescope['coords']['local']['__data__'], dtype=np.float32)
    # Reshape into ant,column
    coords_local = coords_local.reshape(coords_local.size/4,4)
    ant_coords = coords_local[:,1:]
    inputs = np.array(telescope['inputs']['__data__'], dtype=np.float32)
    # Reshape into ant,pol,column
    inputs      = inputs.reshape(inputs.size/7/2,2,7)
    delays      = inputs[:,:,5]*1e-9
    dispersions = inputs[:,:,6]*1e-9
    return telescope, ant_coords, delays, dispersions

class TestDadaBlock(unittest.TestCase):
    """Test the ability of the Dada block to read
        in data that is compatible with other blocks."""
    def setUp(self):
        self.blocks = []
        self.blocks.append(
            (DadaReadBlock(
                "/data1/mcranmer/data/real/leda/2016_xaa.dada"),
            [], [0]))
    def test_read_and_write(self):
        """Reads in a dada file, and logs in ascii
            file."""
        logfile = '.log.txt'
        self.blocks.append((WriteAsciiBlock(logfile), [0], []))
        Pipeline(self.blocks).main() 
        test_bytes = open(logfile, 'r').read(500).split(' ')
        self.assertAlmostEqual(np.float(test_bytes[0]), 3908.5, 3)
    def test_read_copy_write(self):
        """Adds another intermediate block to the
            last step."""
        logfile = '.log.txt'
        self.blocks.append((CopyBlock(), [0], [1, 2, 3]))
        self.blocks.append((WriteAsciiBlock(logfile), [3], []))
        Pipeline(self.blocks).main() 
        test_bytes = open(logfile, 'r').read(500).split(' ')
        self.assertAlmostEqual(np.float(test_bytes[0]), 3908.5, 3)
class TestNewDadaReadBlock(unittest.TestCase):
    """Test the ability of the Dada block to read
        in data that is compatible with other blocks."""
    def setUp(self):
        """Reads in one channel of a dada file, and logs in ascii
            file."""
        self.logfile = '.log.txt'
        dadafile = '/data1/hg/dada_plot/2016-02-03-22_37_50_0001287429875776.dada'
        self.blocks = []
        self.blocks.append((NewDadaReadBlock(dadafile, output_chans=[42], time_steps=1), [], [0]))
        self.blocks.append((WriteAsciiBlock(self.logfile), [0], []))
        Pipeline(self.blocks).main() 
    def test_read_and_write(self):
        """Make sure some data is being written"""
        dumpsize = os.path.getsize(self.logfile)
        self.assertGreater(dumpsize, 100)
    def test_imaging(self):
        """Try to grid and image the data"""
        baseline_visibilities = np.loadtxt(self.logfile, dtype=np.float32).view(np.complex64)
        n_stations = 256
        n_baselines = n_stations*(n_stations+1)//2
        baseline_visibilities = baseline_visibilities.reshape(
            (n_baselines, 2, 2))[:, 0, 0]
        redundant_visibilities = np.zeros(shape=[n_stations, n_stations]).astype(np.complex64)
        for i in range(n_stations):
            for j in range(i+1):
                baseline_index = i*(i+1)//2 + j
                redundant_visibilities[i, j] = baseline_visibilities[baseline_index]
                redundant_visibilities[j, i] = np.conj(baseline_visibilities[baseline_index])
        antenna_coordinates = load_telescope("/data1/mcranmer/data/real/leda/lwa_ovro.telescope.json")[1]
        identity_matrix = np.ones((n_stations, n_stations, 3), dtype=np.float32)
        baselines_xyz = (identity_matrix*antenna_coordinates)-(identity_matrix*antenna_coordinates).transpose((1, 0, 2))
        baselines_u = baselines_xyz[:, :, 0].reshape(-1)
        baselines_v = baselines_xyz[:, :, 1].reshape(-1)
        real_visibilities = redundant_visibilities.reshape(-1).view(np.float32)[0::2]
        imaginary_visibilities = redundant_visibilities.reshape(-1).view(np.float32)[1::2]
        out_data = np.zeros(shape=[redundant_visibilities.size*4]).astype(np.float32)
        out_data[0::4] = baselines_u
        out_data[1::4] = baselines_v
        out_data[2::4] = real_visibilities
        out_data[3::4] = imaginary_visibilities 
        blocks = []
        gridding_shape = (512, 512)
        blocks.append((TestingBlock(out_data), [], [0]))
        blocks.append((NearestNeighborGriddingBlock(gridding_shape), [0], [1]))
        blocks.append((WriteAsciiBlock('.log.txt'), [1], []))
        Pipeline(blocks).main()
        model = np.loadtxt('.log.txt').astype(np.float32).view(np.complex64)
        model = model.reshape(gridding_shape)
        # Should be the size of the desired grid
        self.assertEqual(model.size, np.product(gridding_shape))
        brightness = np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(model))))
        # Should be many nonzero elements in the image
        self.assertGreater(brightness[brightness > 1e-30].size, 100)
        # Should be some bright sources
        from matplotlib.image import imsave
        imsave('model.png', brightness)
