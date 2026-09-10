"""Procedural fixtures: no user art, paid generation, or network required."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from _sprite_common import durations_ms, has_useful_transparency, parse_action_spec


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = self.base / 'run'
        self.master = self.base / 'master.png'
        image = Image.new('RGBA', (64, 64))
        ImageDraw.Draw(image).rectangle((26, 20, 35, 49), fill='red')
        image.save(self.master)
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--character-name', 'Fixture',
                 '--master', self.master, '--approve-master', '--pixel-art', '--source-slot-size', '64',
                 '--action', 'run:4:10:loop:2x2')

    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *map(str, args)],
                                text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def read(self, path):
        return json.loads(path.read_text())

    def write(self, path, value):
        path.write_text(json.dumps(value))

    def sheet(self, name='source', jump=False, sword=False, clipped=False, unused=False, opaque=False):
        image = Image.new('RGBA', (128, 128), (255, 0, 255, 255) if opaque else (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for i in range(4):
            x, y = (i % 2) * 64, (i // 2) * 64
            if unused and i == 3:
                draw.rectangle((x + 10, y + 10, x + 12, y + 12), fill='red')
                continue
            lift = i * 4 if jump else 0
            draw.rectangle((x + 26, y + 20 - lift, x + 35, y + 49 - lift), fill='red')
            if sword or i % 2:
                draw.rectangle((x + 36, y + 29 - lift, x + (63 if clipped else 56), y + 31 - lift), fill='blue')
        path = self.base / (name + '.png')
        image.save(path)
        return path

    def candidate(self, action='run', candidate='one'):
        return self.run / 'actions' / action / 'candidates' / candidate

    def process(self, path=None, action='run', candidate='one', *args, ok=True):
        return self.cli('process_action_sheet.py', '--run-dir', self.run, '--action', action,
                        '--candidate', candidate, '--input', path or self.sheet(), *args, ok=ok)

    def review(self, action='run', candidate='one'):
        common = ['--run-dir', self.run, '--action', action, '--candidate', candidate]
        self.cli('qc_action.py', *common)
        self.cli('render_action_preview.py', *common)
        self.cli('select_candidate.py', *common, '--approve-visual', '--accept-qc-review',
                 '--note', 'Synthetic fixture approval for regression testing only.')

    def package(self, ok=True):
        return self.cli('pack_atlas.py', '--run-dir', self.run, '--output-dir', self.base / 'final',
                        '--godot-resource-path', 'res://atlas.png', '--force', ok=ok)

    def add_action(self, action):
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--action', action)

    def test_full_pipeline_and_cross_action_scale(self):
        self.process()
        self.review()
        self.add_action('attack:4:10:once:2x2')
        self.process(self.sheet('attack', sword=True), 'attack')
        self.review('attack')
        self.package()
        for action in ('run', 'attack'):
            im = Image.open(self.candidate(action) / 'frames/0001.png').convert('RGBA')
            red = [(x, y) for y in range(im.height) for x in range(im.width)
                   if im.getpixel((x, y)) == (255, 0, 0, 255)]
            self.assertEqual((min(x for x, y in red), max(x for x, y in red)), (52, 71))
        atlas = self.read(self.base / 'final/atlas.json')
        self.assertEqual(atlas['animations'][0]['pivot'], {'x': 64.0, 'y': 104.96})
        self.assertAlmostEqual(atlas['animations'][0]['godot_offset']['y'], -40.96)

    def test_airborne_displacement_is_preserved(self):
        config = self.base / 'motion.json'
        self.write(config, {'qc_profile': 'aerial', 'contacts': ['airborne'] * 4})
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--action-config', f'run={config}')
        self.process(self.sheet(jump=True))
        bboxes = [Image.open(self.candidate() / f'frames/{i:04d}.png').getbbox() for i in range(1, 5)]
        self.assertEqual([b[1] for b in bboxes], [40, 32, 24, 16])
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'run', '--candidate', 'one')
        qc = self.read(self.candidate() / 'qc.json')
        self.assertFalse(any(w['code'] == 'ground-contact-review' for w in qc['warnings']))

    def test_timing_events_and_one_shot_gif(self):
        self.add_action('attack:4:10:once:2x2')
        config = self.base / 'timing.json'
        self.write(config, {'durations_ms': [120, 40, 60, 180],
                            'phases': ['anticipation', 'contact', 'follow-through', 'recovery'],
                            'contacts': ['both', 'left', 'left', 'both'],
                            'events': [{'frame': 2, 'name': 'hit'}]})
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--action-config', f'attack={config}')
        self.process(); self.review()
        self.process(self.sheet(jump=True), 'attack'); self.review('attack'); self.package()
        animation = self.read(self.base / 'final/atlas.json')['animations'][1]
        self.assertEqual([f['duration_ms'] for f in animation['frames']], [120, 40, 60, 180])
        self.assertEqual(animation['events'], [{'frame': 2, 'name': 'hit', 'time_ms': 120}])
        resource = (self.base / 'final/sprite_frames.tres').read_text()
        self.assertIn('"duration": 0.4', resource)
        gif = Image.open(self.candidate('attack') / 'qa/preview.gif')
        self.assertNotIn('loop', gif.info)
        observed = []
        for i in range(gif.n_frames):
            gif.seek(i); observed.append(gif.info['duration'])
        self.assertEqual(observed, [120, 40, 60, 180])
        gif.close()

    def test_frame_tampering_blocks_packaging(self):
        self.process(); self.review()
        frame = self.candidate() / 'frames/0001.png'
        image = Image.open(frame).convert('RGBA'); image.putpixel((0, 0), (1, 2, 3, 255)); image.save(frame)
        self.assertIn('artifacts changed', self.package(ok=False).stderr)

    def test_preview_tampering_blocks_selection(self):
        self.process(); self.review()
        (self.candidate() / 'qa/preview.gif').write_bytes(b'changed')
        self.assertIn('Preview artifacts changed', self.package(ok=False).stderr)

    def test_qc_tampering_blocks_old_approval(self):
        self.process(); self.review()
        qc_path = self.candidate() / 'qc.json'
        qc = self.read(qc_path); qc['extra_note'] = 'changed'; self.write(qc_path, qc)
        self.assertIn('Approval is missing or stale', self.package(ok=False).stderr)

    def test_master_tampering_blocks_packaging(self):
        self.process(); self.review()
        path = self.run / 'references/canonical-master.png'
        image = Image.open(path).convert('RGBA'); image.putpixel((24, 20), (1, 2, 3, 255)); image.save(path)
        self.assertIn('Canonical master changed', self.package(ok=False).stderr)

    def test_config_update_invalidates_selection(self):
        self.process(); self.review()
        path = self.base / 'timing.json'; self.write(path, {'durations_ms': [200] * 4})
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--action-config', f'run={path}')
        self.assertNotIn('selected_candidate', self.read(self.run / 'actions/run/action.json'))
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'run', '--candidate', 'one', ok=False)

    def test_pose_reference_update_preserves_geometry_and_invalidates_only_target(self):
        self.process(); self.review()
        self.add_action('idle:4:10:loop:2x2')
        self.process(action='idle'); self.review('idle')
        action_dir = self.run / 'actions/run'
        anchor = (action_dir / 'references/anchor-sheet.png').read_bytes()
        layout = (action_dir / 'references/layout-guide.png').read_bytes()
        source = (self.candidate() / 'source.png').read_bytes()
        guide = self.sheet('motion-guide', jump=True)
        config = self.base / 'motion.json'
        self.write(config, {'durations_ms': [120, 40, 60, 180]})
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update',
                 '--pose-guide', f'run={guide}', '--action-config', f'run={config}')
        action = self.read(action_dir / 'action.json')
        summary = self.read(self.run / 'run.json')['actions'][0]
        self.assertEqual(action, summary)
        self.assertEqual(action['pose_guide'], 'references/pose-guide.png')
        self.assertEqual(action['durations_ms'], [120, 40, 60, 180])
        self.assertNotIn('selected_candidate', action)
        self.assertNotIn('visual_review', action)
        self.assertEqual(Image.open(action_dir / action['pose_guide']).tobytes(), Image.open(guide).tobytes())
        self.assertEqual(anchor, (action_dir / 'references/anchor-sheet.png').read_bytes())
        self.assertEqual(layout, (action_dir / 'references/layout-guide.png').read_bytes())
        self.assertEqual(source, (self.candidate() / 'source.png').read_bytes())
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'run', '--candidate', 'one', ok=False)
        self.assertEqual(self.read(self.run / 'actions/idle/action.json')['selected_candidate'], 'one')
        self.process(candidate='two'); self.review(candidate='two'); self.package()

    def test_pose_guide_creation_and_replacement_remain_separate_from_anchor(self):
        first = self.sheet('first-guide', jump=True)
        other = self.base / 'guided'
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--character-name', 'Guided',
                 '--master', self.master, '--approve-master', '--action', 'walk:4:10:loop:2x2',
                 '--pose-guide', f'walk={first}')
        action_dir = other / 'actions/walk'
        reference = action_dir / 'references/pose-guide.png'
        self.assertEqual(Image.open(reference).tobytes(), Image.open(first).tobytes())
        self.assertNotEqual(reference.read_bytes(), (action_dir / 'references/anchor-sheet.png').read_bytes())
        second = self.sheet('second-guide', sword=True)
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--update', '--pose-guide', f'walk={second}')
        self.assertEqual(Image.open(reference).tobytes(), Image.open(second).tobytes())
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--update', '--pose-guide', f'walk={reference}')
        self.assertEqual(Image.open(reference).tobytes(), Image.open(second).tobytes())
        # A later master replacement must retain the updated motion reference.
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--master', self.master,
                 '--approve-master', '--replace-master')
        self.assertEqual(Image.open(reference).tobytes(), Image.open(second).tobytes())
        self.assertEqual(self.read(other / 'run.json')['actions'][0]['pose_guide'], 'references/pose-guide.png')

    def test_invalid_pose_guides_do_not_mutate_approved_run(self):
        self.process(); self.review()
        valid = self.sheet('valid-guide')
        broken = self.base / 'broken.png'; broken.write_bytes(b'not an image')
        before = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        cases = [
            [f'unknown={valid}'], [f'run={self.base / "missing.png"}'], [f'run={broken}'],
            [f'run={valid}', f'run={valid}'], [f'run={valid}', f'idle={broken}'],
        ]
        for mappings in cases:
            with self.subTest(mappings=mappings):
                flags = [part for mapping in mappings for part in ('--pose-guide', mapping)]
                self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update',
                         '--action', 'idle:4:10:loop:2x2', *flags, ok=False)
                after = {p.relative_to(self.run): p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
                self.assertEqual(before, after)
        self.package()

    def test_invalid_pose_guide_creation_leaves_no_run(self):
        for mapping in [f'unknown={self.master}', f'run={self.base / "missing.png"}']:
            other = self.base / 'invalid-run'
            self.cli('prepare_sprite_run.py', '--output-dir', other, '--character-name', 'Invalid',
                     '--action', 'run:4:10:loop:2x2', '--pose-guide', mapping, ok=False)
            self.assertFalse(other.exists())

    def test_jpeg_motion_reference_is_stored_as_png(self):
        guide = self.base / 'motion.jpg'
        Image.open(self.sheet(jump=True)).convert('RGB').save(guide)
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--pose-guide', f'run={guide}')
        with Image.open(self.run / 'actions/run/references/pose-guide.png') as stored:
            self.assertEqual(stored.format, 'PNG')
            self.assertEqual(stored.convert('RGB').tobytes(), Image.open(guide).tobytes())

    def test_same_pose_guide_keeps_approval_and_prompt(self):
        guide = self.sheet('guide', jump=True)
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--pose-guide', f'run={guide}')
        self.process(); self.review()
        action_dir = self.run / 'actions/run'
        before = (action_dir / 'action.json').read_bytes()
        prompt = (action_dir / 'prompt.md').read_bytes()
        for path in (guide, action_dir / 'references/pose-guide.png'):
            self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--pose-guide', f'run={path}')
            self.assertEqual(before, (action_dir / 'action.json').read_bytes())
            self.assertEqual(prompt, (action_dir / 'prompt.md').read_bytes())
            self.package()

    def test_pose_update_without_master_remains_blocked(self):
        other = self.base / 'no-master'
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--character-name', 'Waiting',
                 '--action', 'walk:4:10:loop:2x2')
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--update',
                 '--pose-guide', f'walk={self.sheet(jump=True)}')
        run = self.read(other / 'run.json')
        self.assertEqual(run['status'], 'needs-master')
        self.assertEqual(run['actions'][0]['status'], 'blocked-on-master')
        self.assertEqual(self.read(other / 'actions/walk/action.json')['status'], 'blocked-on-master')

    def test_source_clipping_is_not_hidden_by_normalization(self):
        self.process(self.sheet(clipped=True))
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'run', '--candidate', 'one', ok=False)
        self.assertIn('source-slot-clipping', str(self.read(self.candidate() / 'qc.json')['errors']))

    def test_unused_grid_slot_is_checked(self):
        self.add_action('short:3:10:once:2x2')
        self.process(self.sheet(unused=True), 'short')
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'short', '--candidate', 'one', ok=False)
        self.assertIn('content-in-unused-slots', str(self.read(self.candidate('short') / 'qc.json')['errors']))

    def test_fixed_grid_rejects_non_square_slots(self):
        image = Image.open(self.sheet()); path = self.base / 'wrong.png'; image.resize((128, 96)).save(path)
        self.assertIn('equal square source slots', self.process(path, ok=False).stderr)

    def test_no_silent_chroma_on_native_path(self):
        self.assertIn('Expected real alpha', self.process(self.sheet(opaque=True), ok=False).stderr)

    def test_transparency_flag_is_validated(self):
        self.assertIn('real transparent background', self.process(self.sheet(opaque=True), 'run', 'one', '--already-transparent', ok=False).stderr)

    def test_rebuild_clears_approval_and_stale_frames(self):
        path = self.sheet(); self.process(path); self.review()
        Image.new('RGBA', (128, 128)).save(self.candidate() / 'frames/9999.png')
        self.process(path, 'run', 'one', '--force')
        self.assertFalse((self.candidate() / 'frames/9999.png').exists())
        self.assertFalse((self.candidate() / 'qc.json').exists())
        self.package(ok=False)

    def test_second_candidate_preserves_approved_selection(self):
        self.process(); self.review(); self.process(self.sheet('two', jump=True), candidate='two')
        self.assertEqual(self.read(self.run / 'actions/run/action.json')['selected_candidate'], 'one')
        self.package()

    def test_reattaching_same_master_is_noop(self):
        self.process(); self.review()
        before = (self.run / 'run.json').read_bytes()
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--master', self.master, '--approve-master')
        self.assertEqual(before, (self.run / 'run.json').read_bytes())
        self.package()

    def test_mirror_keeps_order_and_timing(self):
        self.process(self.sheet(jump=True)); self.review()
        self.add_action('left:4:10:loop:2x2')
        self.cli('mirror_action.py', '--run-dir', self.run, '--source-action', 'run', '--target-action', 'left',
                 '--confirm-safe-mirror', '--note', 'Procedural symmetric identity fixture.')
        for i in range(1, 5):
            left = Image.open(self.candidate('left', 'derived-mirror-01') / f'frames/{i:04d}.png').convert('RGBA')
            expected = Image.open(self.candidate() / f'frames/{i:04d}.png').transpose(Image.Transpose.FLIP_LEFT_RIGHT).convert('RGBA')
            self.assertEqual(left.tobytes(), expected.tobytes())
        self.review('left', 'derived-mirror-01'); self.package()

    def test_legacy_run_remains_explicit_review(self):
        run = self.read(self.run / 'run.json')
        run['schema_version'] = 1
        run['output'].pop('placement'); run['output'].pop('pivot'); run['output'].pop('source_pivot')
        self.write(self.run / 'run.json', run)
        self.process(); self.review(); self.package()
        self.assertIn('legacy-action-fit', str(self.read(self.candidate() / 'qc.json')['warnings']))

    def test_legacy_unsigned_processing_cannot_be_approved(self):
        self.process()
        path = self.candidate() / 'processing.json'; data = self.read(path); data.pop('input_fingerprint'); self.write(path, data)
        self.assertIn('legacy evidence is unsigned', self.cli('qc_action.py', '--run-dir', self.run,
                                                            '--action', 'run', '--candidate', 'one', ok=False).stderr)

    def test_custom_root_and_rectangular_canvas(self):
        run = self.read(self.run / 'run.json')
        run['output']['frame_width'] = 160
        run['output']['pivot'] = [70, 100]
        self.write(self.run / 'run.json', run)
        self.process(self.sheet(jump=True)); self.review(); self.package()
        image = Image.open(self.candidate() / 'frames/0001.png')
        self.assertEqual(image.size, (160, 128))
        self.assertEqual(image.getbbox(), (58, 35, 78, 95))
        animation = self.read(self.base / 'final/atlas.json')['animations'][0]
        self.assertEqual(animation['pivot'], {'x': 70, 'y': 100})
        self.assertEqual(animation['godot_offset'], {'x': 10, 'y': -36})

    def test_custom_root_mirror(self):
        run = self.read(self.run / 'run.json'); run['output']['pivot'] = [60, 100]
        self.write(self.run / 'run.json', run)
        self.process(); self.review(); self.add_action('left:4:10:loop:2x2')
        self.cli('mirror_action.py', '--run-dir', self.run, '--source-action', 'run', '--target-action', 'left',
                 '--confirm-safe-mirror', '--note', 'Symmetric fixture with custom root.')
        image = Image.open(self.candidate('left', 'derived-mirror-01') / 'frames/0001.png')
        self.assertEqual(image.getbbox(), (52, 35, 72, 95))
        self.review('left', 'derived-mirror-01'); self.package()

    def test_mirror_clipping_is_rejected(self):
        run = self.read(self.run / 'run.json'); run['output']['pivot'] = [48, 100]
        self.write(self.run / 'run.json', run)
        self.process(); self.review(); self.add_action('left:4:10:loop:2x2')
        self.cli('mirror_action.py', '--run-dir', self.run, '--source-action', 'run', '--target-action', 'left',
                 '--confirm-safe-mirror', '--note', 'Fixture deliberately exceeds mirrored canvas.')
        self.cli('qc_action.py', '--run-dir', self.run, '--action', 'left', '--candidate', 'derived-mirror-01', ok=False)
        self.assertIn('paste-clamped', str(self.read(self.candidate('left', 'derived-mirror-01') / 'qc.json')['errors']))

    def test_center_anchor_guide_and_export(self):
        other = self.base / 'centered'
        self.cli('prepare_sprite_run.py', '--output-dir', other, '--character-name', 'Center',
                 '--master', self.master, '--approve-master', '--anchor', 'center',
                 '--action', 'run:4:10:loop:2x2', '--source-slot-size', '64')
        self.run = other
        guide = Image.open(self.run / 'actions/run/references/anchor-sheet.png')
        bbox = guide.crop((0, 0, 64, 64)).getbbox()
        self.assertAlmostEqual((bbox[1] + bbox[3]) / 2, 32, delta=0.5)
        self.process(); self.review(); self.package()
        self.assertEqual(self.read(self.base / 'final/atlas.json')['animations'][0]['pivot'], {'x': 64, 'y': 64})

    def test_source_resolution_does_not_change_body_scale(self):
        original = self.sheet(); doubled = self.base / 'double.png'
        Image.open(original).resize((256, 256), Image.Resampling.NEAREST).save(doubled)
        self.process(original); self.process(doubled, candidate='double')
        for i in range(1, 5):
            one = Image.open(self.candidate() / f'frames/{i:04d}.png')
            two = Image.open(self.candidate(candidate='double') / f'frames/{i:04d}.png')
            self.assertEqual(one.tobytes(), two.tobytes())

    def test_issued_prompt_is_preserved(self):
        path = self.base / 'issued.txt'; path.write_text('Exact fixture generation prompt.')
        self.process(self.sheet(), 'run', 'one', '--prompt-file', path)
        self.assertEqual((self.candidate() / 'prompt-used.md').read_text(), path.read_text())
        self.assertEqual(self.read(self.candidate() / 'processing.json')['prompt_origin'], 'issued-prompt-file')

    def test_changed_master_requires_explicit_replacement(self):
        self.process(); self.review()
        path = self.run / 'references/canonical-master.png'
        image = Image.open(path).convert('RGBA'); image.putpixel((24, 20), (1, 2, 3, 255)); image.save(path)
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--master', path, '--approve-master', ok=False)
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--master', path, '--approve-master', '--replace-master')
        self.assertNotIn('selected_candidate', self.read(self.run / 'actions/run/action.json'))

    def test_update_rejects_ignored_geometry_flags(self):
        before = (self.run / 'run.json').read_bytes()
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--pivot', '10,20', ok=False)
        self.assertEqual(before, (self.run / 'run.json').read_bytes())

    def test_chroma_helper_integration(self):
        helper = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'skills/.system/imagegen/scripts/remove_chroma_key.py'
        if not helper.is_file():
            self.skipTest('Installed imagegen chroma helper not available.')
        run = self.read(self.run / 'run.json'); run['chroma_key'] = '#FF00FF'; self.write(self.run / 'run.json', run)
        self.process(self.sheet(opaque=True), 'run', 'one', '--remove-chroma')
        self.assertTrue(self.read(self.candidate() / 'processing.json')['chroma_removed'])
        self.assertEqual(Image.open(self.candidate() / 'frames/0001.png').getpixel((0, 0)), (0, 0, 0, 0))
        self.review(); self.package()

    @unittest.skipUnless(os.environ.get('SPRITE_TEST_GODOT'), 'Set SPRITE_TEST_GODOT for real Godot import validation.')
    def test_godot_resource_loads_and_preserves_timing(self):
        config = self.base / 'timing.json'; self.write(config, {'durations_ms': [120, 40, 60, 180]})
        self.cli('prepare_sprite_run.py', '--output-dir', self.run, '--update', '--action-config', f'run={config}')
        self.process(self.sheet(jump=True)); self.review(); self.package()
        project = self.base / 'final'
        (project / 'project.godot').write_text('[application]\nconfig/name="Sprite regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        (project / 'verify.gd').write_text("""extends SceneTree
func _initialize():
    var frames = load("res://sprite_frames.tres") as SpriteFrames
    if frames == null or frames.get_frame_count("run") != 4:
        quit(1)
        return
    var milliseconds = [120.0, 40.0, 60.0, 180.0]
    for i in range(4):
        var actual = frames.get_frame_duration("run", i) / frames.get_animation_speed("run") * 1000.0
        if abs(actual - milliseconds[i]) > 0.001:
            quit(2)
            return
    var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://atlas.json"))
    var sprite = AnimatedSprite2D.new()
    sprite.sprite_frames = frames
    var offset = manifest.animations[0].godot_offset
    sprite.offset = Vector2(offset.x, offset.y)
    if abs(sprite.offset.y + 40.96) > 0.001:
        quit(3)
        return
    sprite.free()
    print("GODOT_SPRITE_REGRESSION_OK")
    quit(0)
""")
        godot = os.environ['SPRITE_TEST_GODOT']
        imported = subprocess.run([godot, '--headless', '--log-file', str(project / 'import.log'), '--path', str(project), '--editor', '--import'],
                                  capture_output=True, text=True, timeout=55)
        self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
        loaded = subprocess.run([godot, '--headless', '--log-file', str(project / 'run.log'), '--path', str(project), '--script', 'res://verify.gd'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(loaded.returncode, 0, loaded.stdout + loaded.stderr)
        self.assertIn('GODOT_SPRITE_REGRESSION_OK', loaded.stdout)

    def test_cli_help(self):
        for path in (ROOT / 'scripts').glob('*.py'):
            if not path.name.startswith('_'):
                with self.subTest(script=path.name): self.cli(path.name, '--help')


class ValidationTest(unittest.TestCase):
    def test_nonfinite_timing_rejected(self):
        for fps in ['nan', 'inf', '-1', '0']:
            with self.assertRaises(ValueError): parse_action_spec(f'run:4:{fps}:loop')
        for values in [[10, 20], [10, -1, 20, 30], [10, float('nan'), 20, 30], [10, True, 20, 30]]:
            with self.assertRaises(SystemExit): durations_ms({'fps': 10, 'frame_count': 4, 'durations_ms': values})

    def test_one_transparent_pixel_does_not_make_a_cutout(self):
        image = Image.new('RGBA', (64, 64), 'red'); image.putpixel((0, 0), (0, 0, 0, 0))
        self.assertFalse(has_useful_transparency(image))


if __name__ == '__main__':
    unittest.main()
