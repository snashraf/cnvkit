#!/usr/bin/env python
"""Unit tests for the CNVkit library, cnvlib."""
from __future__ import absolute_import, division, print_function

import unittest

import numpy as np

import cnvlib
from cnvlib.genome import GenomicArray
# Import all modules as a smoke test
from cnvlib import (access, antitarget, cnary, commands, core, coverage,
                    diagram, export, fix, importers, metrics, params, plots,
                    reference, reports, segmentation, smoothing, tabio, vary)


class CNATests(unittest.TestCase):
    """Tests for the CopyNumArray class."""

    def test_empty(self):
        """Instantiate from an empty file."""
        cnarr = tabio.read_cna("formats/empty")
        self.assertEqual(len(cnarr), 0)

    def test_basic(self):
        """Test basic container functionality and magic methods."""
        cna = tabio.read_cna('formats/reference-tr.cnn')
        # Length
        self.assertEqual(len(cna),
                         linecount('formats/reference-tr.cnn') - 1)
        # Equality
        same = tabio.read_cna('formats/reference-tr.cnn')
        self.assertEqual(cna, same)
        # Item access
        orig = cna[0]
        cna[0] = orig
        cna[3:4] = cna[3:4]
        cna[6:10] = cna[6:10]
        self.assertEqual(tuple(cna[0]), tuple(same[0]))
        self.assertEqual(cna[3:6], same[3:6])

    def test_center_all(self):
        """Test recentering."""
        cna = tabio.read_cna('formats/reference-tr.cnn')
        # Median-centering an already median-centered array -> no change
        chr1 = cna.in_range('chr1')
        self.assertAlmostEqual(0, np.median(chr1['log2']), places=1)
        chr1.center_all()
        orig_chr1_cvg = np.median(chr1['log2'])
        self.assertAlmostEqual(0, orig_chr1_cvg)
        # Median-centering resets a shift away from the median
        chr1plus2 = chr1.copy()
        chr1plus2['log2'] += 2.0
        chr1plus2.center_all()
        self.assertAlmostEqual(np.median(chr1plus2['log2']), orig_chr1_cvg)
        # Other methods for centering are similar for a CN-neutral chromosome
        for method in ("mean", "mode", "biweight"):
            cp = chr1.copy()
            cp.center_all(method)
            self.assertLess(abs(cp['log2'].median() - orig_chr1_cvg), 0.1)

    def test_drop_extra_columns(self):
        """Test removal of optional 'gc' column."""
        cna = tabio.read_cna('formats/reference-tr.cnn')
        self.assertIn('gc', cna)
        cleaned = cna.drop_extra_columns()
        self.assertNotIn('gc', cleaned)
        self.assertTrue((cleaned['log2'] == cna['log2']).all())

    def test_gender(self):
        """Guess chromosomal gender from chrX log2 ratio value."""
        for (fname, sample_is_f, ref_is_m) in (
                ("formats/f-on-f.cns", True, False),
                ("formats/f-on-m.cns", True, True),
                ("formats/m-on-f.cns", False, False),
                ("formats/m-on-m.cns", False, True),
                ("formats/amplicon.cnr", False, True),
                ("formats/cl_seq.cns", True, True),
                ("formats/tr95t.cns", True, True),
                ("formats/reference-tr.cnn", False, False),
            ):
            guess = tabio.read_cna(fname).guess_xx(ref_is_m)
            self.assertEqual(guess, sample_is_f,
                             "%s: guessed XX %s but is %s"
                             % (fname, guess, sample_is_f))

    def test_residuals(self):
        cnarr = tabio.read_cna("formats/amplicon.cnr")
        segments = tabio.read_cna("formats/amplicon.cns")
        regions = GenomicArray(segments.data).drop_extra_columns()
        for arg in (None, segments, regions):
            resid = cnarr.residuals(arg)
            self.assertAlmostEqual(0, resid.mean(), delta=.3)
            self.assertAlmostEqual(1, np.percentile(resid, 80), delta=.2)
            self.assertAlmostEqual(2, resid.std(), delta=.5)



class CommandTests(unittest.TestCase):
    """Tests for top-level commands."""

    def test_access(self):
        fasta = "formats/chrM-Y-trunc.hg19.fa"
        for min_gap_size, expect_nrows in ((None, 3),
                                           (500, 3),
                                           (1000, 2)):
            acc = commands.do_access(fasta, [], min_gap_size)
            self.assertEqual(len(acc), expect_nrows)
        excludes = ["formats/dac-my.bed", "formats/duke-my.bed"]
        for min_gap_size, expect_nrows in ((None, 5),
                                           (2, 5),
                                           (20, 4),
                                           (200, 3),
                                           (2000, 2)):
            commands.do_access(fasta, excludes, min_gap_size)

    def test_antitarget(self):
        """The 'antitarget' command."""
        baits = tabio.read_auto('formats/nv2_baits.interval_list')
        access = tabio.read_auto('../data/access-5k-mappable.hg19.bed')
        self.assertLess(0, len(commands.do_antitarget(baits)))
        self.assertLess(0, len(commands.do_antitarget(baits, access)))
        self.assertLess(0, len(commands.do_antitarget(baits, access, 200000)))
        self.assertLess(0, len(commands.do_antitarget(baits, access, 10000,
                                                      5000)))

    def test_batch_reference(self):
        """The 'batch' command with an existing reference."""
        ref = cnvlib.read('formats/reference-tr.cnn')
        targets, antitargets = reference.reference2regions(ref)
        self.assertLess(0, len(antitargets))
        self.assertEqual(len(antitargets), (ref['gene'] == 'Background').sum())
        self.assertEqual(len(targets), len(ref) - len(antitargets))

    def test_breaks(self):
        """The 'breaks' command."""
        probes = tabio.read_cna("formats/amplicon.cnr")
        segs = tabio.read_cna("formats/amplicon.cns")
        rows = commands.do_breaks(probes, segs, 4)
        self.assertGreater(len(rows), 0)

    def test_call(self):
        """The 'call' command."""
        # Methods: clonal, threshold, none
        tr_cns = tabio.read_cna("formats/tr95t.cns")
        tr_thresh = commands.do_call(tr_cns, None, "threshold",
                            is_reference_male=True, is_sample_female=True)
        self.assertEqual(len(tr_cns), len(tr_thresh))
        tr_clonal = commands.do_call(tr_cns, None, "clonal",
                            purity=.65,
                            is_reference_male=True, is_sample_female=True)
        self.assertEqual(len(tr_cns), len(tr_clonal))
        cl_cns = tabio.read_cna("formats/cl_seq.cns")
        cl_thresh = commands.do_call(cl_cns, None, "threshold",
                            thresholds=np.log2((np.arange(12) + .5) / 6.),
                            is_reference_male=True, is_sample_female=True)
        self.assertEqual(len(cl_cns), len(cl_thresh))
        cl_clonal = commands.do_call(cl_cns, None, "clonal",
                            ploidy=6, purity=.99,
                            is_reference_male=True, is_sample_female=True)
        self.assertEqual(len(cl_cns), len(cl_clonal))
        cl_none = commands.do_call(cl_cns, None, "none",
                            ploidy=6, purity=.99,
                            is_reference_male=True, is_sample_female=True)
        self.assertEqual(len(cl_cns), len(cl_none))

    def test_call_filter(self):
        segments = cnvlib.read("formats/tr95t.segmetrics.cns")
        variants = tabio.read("formats/na12878_na12882_mix.vcf", "vcf")
        # Each filter individually, then all filters together
        for filters in (['ampdel'], ['cn'], ['ci'], ['sem'],
                        ['sem', 'cn', 'ampdel'],
                        ['ci', 'cn', 'ampdel']):
            result = commands.do_call(segments, variants, method="threshold",
                                      purity=.9, is_reference_male=True,
                                      is_sample_female=True, filters=filters)
            self.assertLessEqual(len(result), len(segments))
            self.assertLessEqual(len(segments.chromosome.unique()), len(result))
            for colname in 'baf', 'cn', 'cn1', 'cn2':
                self.assertIn(colname, result)

    def test_call_gender(self):
        """Test each 'call' method on allosomes."""
        for (fname, sample_is_f, ref_is_m,
             chr1_expect, chrx_expect, chry_expect,
             chr1_cn, chrx_cn, chry_cn,
            ) in (
                ("formats/f-on-f.cns", True, False, 0, 0, None, 2, 2, None),
                ("formats/f-on-m.cns", True, True, 0.585, 1, None, 3, 2, None),
                ("formats/m-on-f.cns", False, False, 0, -1, 0, 2, 1, 1),
                ("formats/m-on-m.cns", False, True, 0, 0, 0, 2, 1, 1),
            ):
            cns = tabio.read_cna(fname)
            chr1_idx = (cns.chromosome == 'chr1')
            chrx_idx = (cns.chromosome == 'chrX')
            chry_idx = (cns.chromosome == 'chrY')
            def test_chrom_means(segments):
                self.assertEqual(chr1_cn, segments['cn'][chr1_idx].mean())
                self.assertAlmostEqual(chr1_expect,
                                       segments['log2'][chr1_idx].mean(), 0)
                self.assertEqual(chrx_cn, segments['cn'][chrx_idx].mean())
                self.assertAlmostEqual(chrx_expect,
                                       segments['log2'][chrx_idx].mean(), 0)
                if not sample_is_f:
                    self.assertEqual(chry_cn, segments['cn'][chry_idx].mean())
                    self.assertAlmostEqual(chry_expect,
                                           segments['log2'][chry_idx].mean(), 0)

            # Call threshold
            cns_thresh = commands.do_call(cns, None, "threshold",
                                 is_reference_male=ref_is_m,
                                 is_sample_female=sample_is_f)
            test_chrom_means(cns_thresh)
            # Call clonal pure
            cns_clone = commands.do_call(cns, None, "clonal",
                                is_reference_male=ref_is_m,
                                is_sample_female=sample_is_f)
            test_chrom_means(cns_clone)
            # Call clonal barely-mixed
            cns_p99 = commands.do_call(cns, None, "clonal", purity=0.99,
                              is_reference_male=ref_is_m,
                              is_sample_female=sample_is_f)
            test_chrom_means(cns_p99)

    def test_coverage(self):
        """The 'coverage' command."""
        # fa = 'formats/chrM-Y-trunc.hg19.fa'
        bed = 'formats/duke-my.bed'
        bam = 'formats/na12878-chrM-Y-trunc.bam'
        for by_count in (False, True):
            for min_mapq in (0, 30):
                for nprocs in (1, 2):
                    cna = commands.do_coverage(bed, bam,
                                               by_count=by_count,
                                               min_mapq=min_mapq,
                                               processes=nprocs)
                    self.assertEqual(len(cna), 4)
                    self.assertTrue((cna.log2 != 0).any())
                    self.assertGreater(cna.log2.nunique(), 1)

    def test_export(self):
        """Run the 'export' command with each format."""
        # SEG
        seg_rows = export.export_seg(["formats/tr95t.cns"])
        self.assertGreater(len(seg_rows), 0)
        seg2_rows = export.export_seg(["formats/tr95t.cns",
                                       "formats/cl_seq.cns"])
        self.assertGreater(len(seg2_rows), len(seg_rows))
        # THetA2
        cnr = tabio.read_cna("formats/tr95t.cns")
        theta_rows = export.export_theta(cnr, None)
        self.assertGreater(len(theta_rows), 0)
        ref = tabio.read_cna("formats/reference-tr.cnn")
        theta_rows = export.export_theta(cnr, ref)
        self.assertGreater(len(theta_rows), 0)
        # Formats that calculate absolute copy number
        for fname, ploidy, is_f in [("tr95t.cns", 2, True),
                                    ("cl_seq.cns", 6, True),
                                    ("amplicon.cns", 2, False)]:
            cns = tabio.read_cna("formats/" + fname)
            # BED
            self.assertLess(len(export.export_bed(cns, ploidy, True, is_f,
                                                  cns.sample_id, "ploidy")),
                            len(cns))
            self.assertLess(len(export.export_bed(cns, ploidy, True, is_f,
                                                  cns.sample_id, "variant")),
                            len(cns))
            self.assertEqual(len(export.export_bed(cns, ploidy, True, is_f,
                                                   cns.sample_id, "all")),
                             len(cns))
            # VCF
            _vheader, vcf_body = export.export_vcf(cns, ploidy, True, is_f)
            self.assertTrue(0 < len(vcf_body.splitlines()) < len(cns))

    def test_fix(self):
        """The 'fix' command."""
        # Extract fake target/antitarget bins from a combined file
        ref = tabio.read_cna('formats/reference-tr.cnn')
        is_bg = (ref["gene"] == "Background")
        tgt_bins = ref[~is_bg]
        tgt_bins.log2 += np.random.randn(len(tgt_bins)) / 5
        anti_bins = ref[is_bg]
        anti_bins.log2 += np.random.randn(len(anti_bins)) / 5
        blank_bins = cnary.CopyNumArray([])
        # Typical usage (hybrid capture)
        cnr = commands.do_fix(tgt_bins, anti_bins, ref)
        self.assertTrue(0 < len(cnr) <= len(ref))
        # Blank antitargets (WGS or amplicon)
        cnr = commands.do_fix(tgt_bins, blank_bins, ref[~is_bg])
        self.assertTrue(0 < len(cnr) <= len(tgt_bins))

    def test_gainloss(self):
        """The 'gainloss' command."""
        probes = tabio.read_cna("formats/amplicon.cnr")
        rows = commands.do_gainloss(probes, male_reference=True)
        self.assertGreater(len(rows), 0)
        segs = tabio.read_cna("formats/amplicon.cns")
        rows = commands.do_gainloss(probes, segs, 0.3, 4, male_reference=True)
        self.assertGreater(len(rows), 0)

    def test_import_theta(self):
        """The 'import-theta' command."""
        cns = tabio.read_cna("formats/nv3.cns")
        theta_fname = "formats/nv3.n3.results"
        for new_cns in commands.do_import_theta(cns, theta_fname):
            self.assertTrue(0 < len(new_cns) <= len(cns))

    def test_metrics(self):
        """The 'metrics' command."""
        cnarr = tabio.read_cna("formats/amplicon.cnr")
        segments = tabio.read_cna("formats/amplicon.cns")
        resids = cnarr.residuals(segments)
        self.assertLessEqual(len(resids), len(cnarr))
        values = metrics.ests_of_scale(resids)
        for val in values:
            self.assertGreater(val, 0)

    def test_reference(self):
        """The 'reference' command."""
        # Empty antitargets
        ref = commands.do_reference(["formats/amplicon.cnr"], ["formats/empty"])
        self.assertGreater(len(ref), 0)
        # Empty antitargets, flat reference
        ref = commands.do_reference_flat("formats/amplicon.bed",
                                         "formats/empty")
        self.assertGreater(len(ref), 0)

    def test_segment(self):
        """The 'segment' command."""
        cnarr = tabio.read_cna("formats/amplicon.cnr")
        # NB: R methods are in another script; haar is pure-Python
        segments = segmentation.do_segmentation(cnarr, "haar")
        self.assertGreater(len(segments), 0)
        segments = segmentation.do_segmentation(cnarr, "haar", threshold=.0001,
                                                skip_low=True)
        self.assertGreater(len(segments), 0)
        varr = tabio.read("formats/na12878_na12882_mix.vcf", "vcf")
        segments = segmentation.do_segmentation(cnarr, "haar", variants=varr)
        self.assertGreater(len(segments), 0)

    def test_segment_parallel(self):
        """The 'segment' command, in parallel."""
        cnarr = tabio.read_cna("formats/amplicon.cnr")
        psegments = segmentation.do_segmentation(cnarr, "haar", processes=2)
        ssegments = segmentation.do_segmentation(cnarr, "haar", processes=1)
        self.assertEqual(psegments.data.shape, ssegments.data.shape)
        self.assertEqual(len(psegments.meta), len(ssegments.meta))

    def test_segmetrics(self):
        """The 'segmetrics' command."""
        cnarr = tabio.read_cna("formats/amplicon.cnr")
        segarr = tabio.read_cna("formats/amplicon.cns")
        for func in (
            lambda x: metrics.confidence_interval_bootstrap(x, 0.05, 100),
            lambda x: metrics.prediction_interval(x, 0.05),
        ):
            lo, hi = commands._segmetric_interval(segarr, cnarr, func)
            self.assertEqual(len(lo), len(segarr))
            self.assertEqual(len(hi), len(segarr))
            sensible_segs_mask = (np.asarray(segarr['probes']) > 3)
            means = segarr[sensible_segs_mask, 'log2']
            los = lo[sensible_segs_mask]
            his = hi[sensible_segs_mask]
            self.assertTrue((los < means).all())
            self.assertTrue((means < his).all())

    def test_target(self):
        """The 'target' command."""
        annot_fname = "formats/refflat-mini.txt"
        for bait_fname in ("formats/nv2_baits.interval_list",
                           "formats/amplicon.bed"):
            baits = tabio.read_auto(bait_fname)
            bait_len = len(baits)
            # No splitting: w/ and w/o re-annotation
            r1 = commands.do_target(baits)
            self.assertEqual(len(r1), bait_len)
            r1a = commands.do_target(baits, do_short_names=True,
                                     annotate=annot_fname)
            self.assertEqual(len(r1a), len(r1))
            # Splitting
            r2 = commands.do_target(baits, do_short_names=True, do_split=True,
                                    avg_size=100)
            self.assertGreater(len(r2), len(r1))
            r2a = commands.do_target(baits, do_short_names=True, do_split=True,
                                     avg_size=100, annotate=annot_fname)
            self.assertEqual(len(r2a), len(r2))
            # Original regions object should be unmodified
            self.assertEqual(len(baits), bait_len)



class OtherTests(unittest.TestCase):
    """Tests for other functionality."""

    def test_fix_edge(self):
        """Test the 'edge' bias correction calculations."""
        # With no gap, gain and loss should balance out
        # 1. Wide target, no secondary corrections triggered
        insert_size = 250
        gap_size = np.zeros(1)  # Adjacent
        target_size = np.asarray([600])
        loss = fix.edge_losses(target_size, insert_size)
        gain = fix.edge_gains(target_size, gap_size, insert_size)
        gain *= 2  # Same on the other side
        self.assertAlmostEqual(loss, gain)
        # 2. Trigger 'loss' correction (target_size < 2 * insert_size)
        target_size = np.asarray([450])
        self.assertAlmostEqual(fix.edge_losses(target_size, insert_size),
                        2 * fix.edge_gains(target_size, gap_size, insert_size))
        # 3. Trigger 'gain' correction (target_size + gap_size < insert_size)
        target_size = np.asarray([300])
        self.assertAlmostEqual(fix.edge_losses(target_size, insert_size),
                        2 * fix.edge_gains(target_size, gap_size, insert_size))

    # call
    # Test: convert_clonal(x, 1, 2) == convert_diploid(x)


# == helpers ==

def linecount(filename):
    i = -1
    with open(filename) as handle:
        for i, _line in enumerate(handle):
            pass
        return i + 1


if __name__ == '__main__':
    unittest.main(verbosity=2)
