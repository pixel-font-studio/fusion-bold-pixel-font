import math

import unidata_blocks
from PIL import ImageFont, Image, ImageDraw
from fontTools.ttLib import TTFont
from loguru import logger
from pixel_font_knife.mono_bitmap import MonoBitmap

from tools import configs
from tools.configs import path_define
from tools.configs.options import FontSize


def dump_fonts(font_size: FontSize):
    for dump_config in configs.dump_configs[font_size]:
        logger.info("Dump glyphs: '{}'", dump_config.dump_dir)
        font = TTFont(dump_config.font_file_path)
        image_font = ImageFont.truetype(dump_config.font_file_path, dump_config.rasterize_size)

        canvas_height = math.ceil((font['hhea'].ascent - font['hhea'].descent) / font['head'].unitsPerEm * dump_config.rasterize_size)
        if (canvas_height - font_size) % 2 != 0:
            canvas_height += 1

        for code_point, glyph_name in font.getBestCmap().items():
            c = chr(code_point)
            block = unidata_blocks.get_block_by_code_point(code_point)
            if not c.isprintable() and block.name != 'Private Use Area':
                continue

            canvas_width = math.ceil(font['hmtx'].metrics[glyph_name][0] / font['head'].unitsPerEm * dump_config.rasterize_size)
            if canvas_width <= 0:
                continue
            elif canvas_width > font_size and block.name != 'Private Use Area':
                canvas_width = font_size

            image = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            ImageDraw.Draw(image).text(dump_config.rasterize_offset, c, fill=(0, 0, 0, 255), font=image_font)

            glyph_file_dir = dump_config.dump_dir.joinpath(f'{block.code_start:04X}-{block.code_end:04X} {block.name}')
            code_name = f'{code_point:04X}'
            if block.name == 'CJK Unified Ideographs':
                glyph_file_dir = glyph_file_dir.joinpath(f'{code_name[0:-2]}-')
            glyph_file_path = glyph_file_dir.joinpath(f'{code_name}.png')
            glyph_file_dir.mkdir(parents=True, exist_ok=True)
            image.save(glyph_file_path)


def apply_fallbacks(font_size: FontSize):
    for fallback_config in configs.fallback_configs[font_size]:
        assert fallback_config.dir_from.is_dir(), f"dump dir not exist: '{fallback_config.dir_from}'"
        logger.info("Fallback glyphs: '{}' '{}' -> '{}'", fallback_config.flavor, fallback_config.dir_from, fallback_config.dir_to)
        for glyph_file_dir_from, _, glyph_file_names in fallback_config.dir_from.walk():
            for glyph_file_name in glyph_file_names:
                if not glyph_file_name.endswith('.png'):
                    continue
                glyph_file_path_from = glyph_file_dir_from.joinpath(glyph_file_name)
                code_name = glyph_file_path_from.stem
                code_point = int(code_name, 16)
                block = unidata_blocks.get_block_by_code_point(code_point)
                glyph_file_dir_to = fallback_config.dir_to.joinpath(f'{block.code_start:04X}-{block.code_end:04X} {block.name}')
                if block.name == 'CJK Unified Ideographs':
                    glyph_file_dir_to = glyph_file_dir_to.joinpath(f'{code_name[0:-2]}-')
                if fallback_config.flavor is not None:
                    glyph_file_name = f'{code_name} {fallback_config.flavor}.png'
                glyph_file_path_to = glyph_file_dir_to.joinpath(glyph_file_name)
                glyph_file_dir_to.mkdir(parents=True, exist_ok=True)
                glyph_file_path_from.copy(glyph_file_path_to)


def bolding_glyphs(font_size: FontSize):
    root_dirs = [
        (
            path_define.ark_pixel_glyphs_dir.joinpath(str(font_size)),
            path_define.ark_pixel_bold_glyphs_dir.joinpath(str(font_size)),
        ),
        (
            path_define.patch_glyphs_dir.joinpath(str(font_size)),
            path_define.patch_bold_glyphs_dir.joinpath(str(font_size)),
        ),
        (
            path_define.fallback_glyphs_dir.joinpath(str(font_size)),
            path_define.fallback_bold_glyphs_dir.joinpath(str(font_size)),
        ),
    ]
    for source_root_dir, target_root_dir in root_dirs:
        if not source_root_dir.is_dir():
            continue

        logger.info("Bolding glyphs: '{}' -> '{}'", source_root_dir, target_root_dir)
        for file_dir, _, file_names in source_root_dir.walk():
            for file_name in file_names:
                if not file_name.endswith('.png'):
                    continue

                source_file_path = file_dir.joinpath(file_name)
                target_file_path = target_root_dir.joinpath(source_file_path.relative_to(source_root_dir))

                bitmap = MonoBitmap.load_png(source_file_path)
                solid_bitmap = bitmap.resize(left=1).plus(bitmap)
                shadow_bitmap = solid_bitmap.minus(bitmap).resize(left=1)
                result_bitmap = solid_bitmap.minus(shadow_bitmap)

                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                result_bitmap.save_png(target_file_path)
