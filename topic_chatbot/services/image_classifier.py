# -*- coding: utf-8 -*-
import io
import logging
from PIL import Image, ImageFilter

_logger = logging.getLogger(__name__)


def classify_image(image_bytes):
    """Classify an image into text_table, diagram, or mixed.

    Returns:
        dict: {
            'category': 'text_table' | 'diagram' | 'mixed',
            'confidence_score': float (0.0=pure text/table, 1.0=pure diagram),
            'details': dict
        }
    """
    if not image_bytes:
        return {
            'category': 'text_table',
            'confidence_score': 0.0,
            'details': {'reason': 'empty_image'}
        }

    try:
        stream = io.BytesIO(image_bytes)
        img = Image.open(stream).convert('L')

        target_w = 400
        aspect = img.height / max(img.width, 1)
        target_h = int(target_w * aspect)
        if target_h < 50:
            target_h = 50
        elif target_h > 800:
            target_h = 800
        small_img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)

        # 1. Edge detection
        edges = small_img.filter(ImageFilter.FIND_EDGES)
        edge_data = list(edges.getdata())
        total_pixels = len(edge_data)
        edge_pixels = sum(1 for p in edge_data if p > 40)
        edge_density = edge_pixels / total_pixels if total_pixels > 0 else 0.0

        # 2. Horizontal Projection Profile
        width = small_img.width
        height = small_img.height
        pixels = list(small_img.getdata())

        row_densities = []
        for y in range(height):
            row_slice = pixels[y * width:(y + 1) * width]
            ink_count = sum(1 for p in row_slice if p < 180)
            row_densities.append(ink_count / width)

        text_lines = 0
        in_line = False
        cur_len = 0
        line_lengths = []
        for density in row_densities:
            if density > 0.08:
                if not in_line:
                    in_line = True
                    text_lines += 1
                cur_len += 1
            else:
                if in_line:
                    in_line = False
                    line_lengths.append(cur_len)
                    cur_len = 0
        if in_line and cur_len > 0:
            line_lengths.append(cur_len)

        total_active_rows = sum(1 for d in row_densities if d > 0.08)
        vertical_fill_ratio = total_active_rows / height if height > 0 else 0.0

        # Heuristic scoring: 0.0 = pure text/table, 1.0 = pure diagram
        # Tables/Text have high vertical fill ratio (lines spread across page)
        # Diagrams have low vertical fill ratio (isolated shapes/boxes with large whitespace)
        if vertical_fill_ratio >= 0.30 and text_lines >= 10:
            score = 0.20  # Strong table / document page
        elif vertical_fill_ratio >= 0.20 and text_lines >= 6:
            score = 0.35  # Moderate text/table
        elif vertical_fill_ratio >= 0.12 and text_lines >= 4:
            score = 0.50  # Mixed: contains both text lines and diagrams/figures
        elif vertical_fill_ratio < 0.12:
            score = 0.85  # Diagram: sparse geometric elements with low fill
        else:
            score = 0.65  # Diagram/Flowchart tendency

        avg_ink = sum(row_densities) / len(row_densities) if row_densities else 0.0
        if vertical_fill_ratio < 0.15 and edge_density > 0.08 and text_lines < 10:
            score = min(score + 0.15, 1.0)
        elif avg_ink > 0.30:
            score = max(score - 0.20, 0.0)

        score = round(max(0.0, min(1.0, score)), 2)

        if score < 0.40:
            category = 'text_table'
        elif score > 0.60:
            category = 'diagram'
        else:
            category = 'mixed'

        details = {
            'text_lines': text_lines,
            'vertical_fill_ratio': round(vertical_fill_ratio, 3),
            'edge_density': round(edge_density, 3),
            'avg_ink': round(avg_ink, 3),
            'image_size': f"{img.width}x{img.height}"
        }

        return {
            'category': category,
            'confidence_score': score,
            'details': details
        }

    except Exception as e:
        _logger.warning("Failed to classify image: %s. Defaulting to text_table.", str(e))
        return {
            'category': 'text_table',
            'confidence_score': 0.2,
            'details': {'error': str(e)}
        }
