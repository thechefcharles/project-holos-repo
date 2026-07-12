"""Step 3b: Grammar classification tests (dual-benchmark validation)."""

import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from holos_tools.geocode.grammar import GrammarClassifier


class TestGrammarClassifier:
    """Test grammar classifier against dual benchmarks."""

    def load_my_benchmark(self):
        """Load my 250-row benchmark."""
        with open('golden/chicago_spending_benchmark.json') as f:
            return json.load(f)

    def load_cowork_benchmark(self):
        """Load Cowork 236-row benchmark."""
        data = []
        with open('golden/geocode_benchmark_wardwise_v1.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

    def test_classifier_on_my_benchmark(self):
        """Test grammar classifier on my 250-row benchmark."""
        benchmark = self.load_my_benchmark()

        predictions = defaultdict(lambda: {'correct': 0, 'total': 0, 'examples': []})

        for row in benchmark:
            location = row['location_text']
            expected = row['expected_grammar']
            result = GrammarClassifier.classify(location)

            predictions[expected]['total'] += 1
            if result.grammar == expected:
                predictions[expected]['correct'] += 1
            else:
                if len(predictions[expected]['examples']) < 3:
                    predictions[expected]['examples'].append({
                        'location': location,
                        'expected': expected,
                        'predicted': result.grammar,
                        'confidence': result.confidence
                    })

        print("\n=== Grammar Classifier on My Benchmark (250 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(predictions.keys()):
            stats = predictions[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct}/{total} ({pct:5.1f}%)")

            if stats['examples']:
                for ex in stats['examples']:
                    print(f"    ✗ {ex['location'][:50]} (expected {ex['expected']}, got {ex['predicted']})")

        print(f"\nOverall accuracy: {total_correct}/{total_rows} ({100*total_correct/total_rows:.1f}%)")
        print(f"Target: ≥85% (regex layer should handle most cases)")

    def test_classifier_on_cowork_benchmark(self):
        """Test grammar classifier on Cowork's 236-row benchmark."""
        benchmark = self.load_cowork_benchmark()

        predictions = defaultdict(lambda: {'correct': 0, 'total': 0, 'examples': []})

        for row in benchmark:
            location = row['location_text']
            expected = row['expected_grammar']
            result = GrammarClassifier.classify(location, ward=row['ward'])

            predictions[expected]['total'] += 1
            if result.grammar == expected:
                predictions[expected]['correct'] += 1
            else:
                if len(predictions[expected]['examples']) < 3:
                    predictions[expected]['examples'].append({
                        'location': location,
                        'expected': expected,
                        'predicted': result.grammar,
                    })

        print("\n=== Grammar Classifier on Cowork Benchmark (236 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(predictions.keys()):
            stats = predictions[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct}/{total} ({pct:5.1f}%)")

            if stats['examples']:
                for ex in stats['examples']:
                    print(f"    ✗ {ex['location'][:50]} (expected {ex['expected']}, got {ex['predicted']})")

        print(f"\nOverall accuracy: {total_correct}/{total_rows} ({100*total_correct/total_rows:.1f}%)")

    def test_grammar_coverage(self):
        """Verify classifier handles all grammar types from both benchmarks."""
        my_bench = self.load_my_benchmark()
        cowork_bench = self.load_cowork_benchmark()

        my_grammars = set(row['expected_grammar'] for row in my_bench)
        cowork_grammars = set(row['expected_grammar'] for row in cowork_bench)
        all_grammars = my_grammars | cowork_grammars

        print(f"\n=== Grammar Coverage Check ===")
        print(f"All grammars to support: {sorted(all_grammars)}")

        for grammar in sorted(all_grammars):
            # Create a sample location for this grammar
            samples = [row for row in my_bench if row['expected_grammar'] == grammar]
            if not samples:
                samples = [row for row in cowork_bench if row['expected_grammar'] == grammar]

            if samples:
                location = samples[0]['location_text']
                result = GrammarClassifier.classify(location)
                status = "✓" if result.grammar == grammar else "✗"
                print(f"  {status} {grammar:25s}: sample '{location[:40]}...'")

    def test_ocr_noise_resilience(self):
        """Test classifier on OCR-noise rows (should still detect grammar correctly)."""
        cowork_bench = self.load_cowork_benchmark()
        ocr_rows = [row for row in cowork_bench if row['ocr_noise'] == 'injected']

        print(f"\n=== OCR Noise Resilience (18 rows with injected noise) ===")
        correct = 0
        for row in ocr_rows:
            location = row['location_text']
            expected = row['expected_grammar']
            result = GrammarClassifier.classify(location)
            if result.grammar == expected:
                correct += 1
            else:
                print(f"  ✗ {location} (expected {expected}, got {result.grammar})")

        print(f"OCR noise handling: {correct}/{len(ocr_rows)} ({100*correct/len(ocr_rows):.1f}%)")
        print(f"Target: ≥80% (OCR corrupts street names, but grammar should still be detectable)")


if __name__ == '__main__':
    tester = TestGrammarClassifier()

    print("=" * 80)
    print("GRAMMAR CLASSIFIER VALIDATION")
    print("=" * 80)

    tester.test_classifier_on_my_benchmark()
    tester.test_classifier_on_cowork_benchmark()
    tester.test_grammar_coverage()
    tester.test_ocr_noise_resilience()

    print("\n" + "=" * 80)
