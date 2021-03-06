"""
BSD 3-Clause License

Copyright (c) 2018, Maël Kimmerlin, Aalto University, Finland
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os

class Input_error(Exception):
    pass

def get_filename(config, section, file, is_dir = False):
        filename = config.get(section, file)
        filename_tmp = filename
        
        #Absolute path, use as is
        if filename.startswith("/"):
            if not os.path.isfile(filename):
                raise Input_error(filename + " does not exist")
            return filename
        
        #Relative path: 
        # if a work directory is given, use this, otherwise use the 
        #current directory
        filename_tmp = filename
        
        #Check if it exists
        if not os.path.isfile(filename_tmp) and not is_dir:
            raise Input_error(filename + " does not exist")
        elif not os.path.isdir(filename_tmp) and is_dir:
            raise Input_error(filename + " does not exist")
        
        return filename_tmp