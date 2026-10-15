"""Extended VU0 macro encodings, independently read from Sony's VU manual.

Only encoding/operands are returned. No floating-point, VU memory, pipeline or
random-number execution is implemented here. See PROVENANCE.md.
"""


def decode_extended(mask, ft, fs, group, variant):
    def zero(*fields):
        if any(fields):
            raise ValueError('reserved nonzero VU macro field')

    def integers(*registers):
        if any(r >= 16 for r in registers):
            raise ValueError('unsupported VU integer register')

    vector = {'vfs': fs, 'vft': ft, 'dest_mask': mask}
    unary = {'vft': ft, 'vfs': fs, 'dest_mask': mask}
    if group in (0, 1, 2, 3, 6):
        stem = {0: 'vadda', 1: 'vsuba', 2: 'vmadda', 3: 'vmsuba', 6: 'vmula'}[group]
        return stem + 'xyzw'[variant], vector
    if group in (4, 5):
        return ('vitof' if group == 4 else 'vftoi') + str((0, 4, 12, 15)[variant]), unary
    if group == 7:
        if variant in (0, 2):
            zero(ft)
            return ('vmulaq' if variant == 0 else 'vmulai'), {'vfs': fs, 'dest_mask': mask}
        if variant == 1:
            return 'vabs', unary
        if mask != 14:
            raise ValueError('VCLIP requires xyz destination mask')
        return 'vclipw', vector
    if group in (8, 9):
        zero(ft)
        stem = ('vadda', 'vmadda', 'vadda', 'vmadda') if group == 8 else (
            'vsuba', 'vmsuba', 'vsuba', 'vmsuba')
        return stem[variant] + ('q' if variant < 2 else 'i'), {'vfs': fs, 'dest_mask': mask}
    if group == 10 and variant < 3:
        return ('vadda', 'vmadda', 'vmula')[variant], vector
    if group == 11:
        if variant < 2:
            return ('vsuba', 'vmsuba')[variant], vector
        if variant == 2:
            if mask != 14:
                raise ValueError('outer product requires xyz destination mask')
            return 'vopmula', vector
        zero(mask, ft, fs)
        return 'vnop', {}
    if group == 12 and variant < 2:
        return ('vmove', 'vmr32')[variant], unary
    if group == 13:
        if variant in (0, 2):
            integers(fs)
            return ('vlqi' if variant == 0 else 'vlqd'), {
                'vft': ft, 'vis': fs, 'dest_mask': mask}
        integers(ft)
        return ('vsqi' if variant == 1 else 'vsqd'), {
            'vfs': fs, 'vit': ft, 'dest_mask': mask}
    if group == 14:
        if variant in (0, 2):
            return ('vdiv' if variant == 0 else 'vrsqrt'), {
                'vfs': fs, 'vft': ft, 'fs_component': mask & 3, 'ft_component': mask >> 2}
        if variant == 1:
            zero(fs, mask & 3)
            return 'vsqrt', {'vft': ft, 'ft_component': mask >> 2}
        zero(mask, ft, fs)
        return 'vwaitq', {}
    if group == 15:
        if variant == 0:
            zero(mask >> 2)
            integers(ft)
            return 'vmtir', {'vit': ft, 'vfs': fs, 'fs_component': mask & 3}
        if variant == 1:
            integers(fs)
            return 'vmfir', {'vft': ft, 'vis': fs, 'dest_mask': mask}
        integers(ft, fs)
        if variant == 2 and mask not in (1, 2, 4, 8):
            raise ValueError('unsupported VILWR component mask')
        return ('vilwr' if variant == 2 else 'viswr'), {
            'vit': ft, 'vis': fs, 'dest_mask': mask}
    if group == 16:
        if variant < 2:
            zero(fs)
            return ('vrnext' if variant == 0 else 'vrget'), {'vft': ft, 'dest_mask': mask}
        zero(ft, mask >> 2)
        return ('vrinit' if variant == 2 else 'vrxor'), {'vfs': fs, 'fs_component': mask & 3}
    raise ValueError('unsupported or reserved extended VU macro encoding')
