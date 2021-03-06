#!/usr/bin/python
# Copyright 2016 The ANGLE Project Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# gen_vk_format_table.py:
#  Code generation for vk format map. See vk_format_map.json for data source.

from datetime import date
import json
import math
import pprint
import os
import re
import sys

sys.path.append('..')
import angle_format

template_table_autogen_cpp = """// GENERATED FILE - DO NOT EDIT.
// Generated by {script_name} using data from {input_file_name}
//
// Copyright {copyright_year} The ANGLE Project Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// {out_file_name}:
//   Queries for full Vulkan format information based on GL format.

#include "libANGLE/renderer/vulkan/vk_format_utils.h"

#include "image_util/copyimage.h"
#include "image_util/generatemip.h"
#include "image_util/loadimage.h"

using namespace angle;

namespace rx
{{

namespace vk
{{

void Format::initialize(RendererVk *renderer,
                        const angle::Format &angleFormat)
{{
    switch (angleFormat.id)
    {{
{format_case_data}
        default:
            UNREACHABLE();
            break;
    }}
}}

}}  // namespace vk

}}  // namespace rx
"""

empty_format_entry_template = """case angle::FormatID::{format_id}:
// This format is not implemented in Vulkan.
break;
"""

format_entry_template = """case angle::FormatID::{format_id}:
internalFormat = {internal_format};
{texture_template}
{buffer_template}
break;
"""

texture_basic_template = """textureFormatID = {texture};
vkTextureFormat = {vk_texture_format};
textureInitializerFunction = {texture_initializer};"""

texture_struct_template="{{{texture}, {vk_texture_format}, {texture_initializer}}}"

texture_fallback_template = """{{
static constexpr TextureFormatInitInfo kInfo[] = {{{texture_list}}};
initTextureFallback(renderer, kInfo, ArraySize(kInfo));
}}"""

buffer_basic_template = """bufferFormatID = {buffer};
vkBufferFormat = {vk_buffer_format};
vkBufferFormatIsPacked = {vk_buffer_format_is_packed};
vertexLoadFunction = {vertex_load_function};
vertexLoadRequiresConversion = {vertex_load_converts};"""

buffer_struct_template="""{{{buffer}, {vk_buffer_format}, {vk_buffer_format_is_packed}, 
{vertex_load_function}, {vertex_load_converts}}}"""

buffer_fallback_template = """{{
static constexpr BufferFormatInitInfo kInfo[] = {{{buffer_list}}};
initBufferFallback(renderer, kInfo, ArraySize(kInfo));
}}"""

def is_packed(format_id):
  return "true" if "_PACK" in format_id else "false"


def gen_format_case(angle, internal_format, vk_json_data):
  vk_map = vk_json_data["map"]
  vk_overrides = vk_json_data["overrides"]
  vk_fallbacks = vk_json_data["fallbacks"]
  args = dict(
      format_id=angle,
      internal_format=internal_format,
      texture_template="",
      buffer_template="")

  if ((angle not in vk_map) and (angle not in vk_overrides) and
      (angle not in vk_fallbacks)) or angle == 'NONE':
    return empty_format_entry_template.format(**args)

  def get_formats(format, type):
    format = vk_overrides.get(format, {}).get(type, format)
    if format not in vk_map:
      return []
    fallbacks = vk_fallbacks.get(format, {}).get(type, [])
    if not isinstance(fallbacks, list):
      fallbacks = [fallbacks]
    return [format] + fallbacks

  def texture_args(format):
    return dict(
        texture="angle::FormatID::" + format,
        vk_texture_format=vk_map[format],
        texture_initializer=angle_format.get_internal_format_initializer(
            internal_format, format))

  def buffer_args(format):
    return dict(
        buffer="angle::FormatID::" + format,
        vk_buffer_format=vk_map[format],
        vk_buffer_format_is_packed=is_packed(vk_map[format]),
        vertex_load_function=angle_format.get_vertex_copy_function(
            angle, format),
        vertex_load_converts='false' if angle == format else 'true',
    )

  textures = get_formats(angle, "texture")
  if len(textures) == 1:
    args.update(texture_template=texture_basic_template)
    args.update(texture_args(textures[0]))
  elif len(textures) > 1:
    args.update(
        texture_template=texture_fallback_template,
        texture_list=", ".join(
            texture_struct_template.format(**texture_args(i))
            for i in textures))

  buffers = get_formats(angle, "buffer")
  if len(buffers) == 1:
    args.update(buffer_template=buffer_basic_template)
    args.update(buffer_args(buffers[0]))
  elif len(buffers) > 1:
    args.update(
        buffer_template=buffer_fallback_template,
        buffer_list=", ".join(
            buffer_struct_template.format(**buffer_args(i)) for i in buffers))

  return format_entry_template.format(**args).format(**args)


input_file_name = 'vk_format_map.json'
out_file_name = 'vk_format_table'

angle_to_gl = angle_format.load_inverse_table(os.path.join('..', 'angle_format_map.json'))
vk_json_data = angle_format.load_json(input_file_name)
vk_cases = [gen_format_case(angle, gl, vk_json_data)
             for angle, gl in sorted(angle_to_gl.iteritems())]

output_cpp = template_table_autogen_cpp.format(
    copyright_year = date.today().year,
    format_case_data = "\n".join(vk_cases),
    script_name = __file__,
    out_file_name = out_file_name,
    input_file_name = input_file_name)

with open(out_file_name + '_autogen.cpp', 'wt') as out_file:
  out_file.write(output_cpp)
  out_file.close()
