import tempfile
import unittest
from pathlib import Path
from service import App, amount_cents, categorize
from webcore import Problem


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=App(str(Path(self.tmp.name)/'ledger.db'),demo=False)
    def tearDown(self): self.tmp.cleanup()
    def test_decimal_money_and_refunds_are_exact(self):
        for description,amount in [('a','0.10'),('b','0.20'),('c','-0.05')]:
            self.app.add({'date':'2026-10-01','description':description,'amount':amount})
        result=self.app.summary('2026-10')
        self.assertEqual((result['net_cents'],result['gross_cents'],result['refund_cents']),(25,30,5))
    def test_import_is_atomic_on_invalid_last_row(self):
        with self.assertRaisesRegex(Problem,'Row 3'):
            self.app.import_csv('date,description,amount\n2026-10-01,Lunch,500\n2026-02-30,Bolt,100')
        self.assertEqual(self.app.transactions('2026-10'),[])
    def test_reimport_and_whitespace_are_deduplicated(self):
        source='date,description,amount\n2026-10-01, Coffee  shop ,500.00\n2026-10-01,coffee shop,500'
        self.assertEqual(self.app.import_csv(source)['inserted'],1)
        self.assertEqual(self.app.import_csv(source)['duplicates'],2)
    def test_budget_is_month_scoped(self):
        self.app.handle('POST','/api/budgets',{},dict(month='2026-10',category='food',amount='2500'))
        self.assertEqual(self.app.summary('2026-10')['budget_cents'],250000)
        self.assertEqual(self.app.summary('2026-11')['budget_cents'],0)
    def test_rejects_non_finite_exponential_and_fractional_kobo(self):
        for value in ['NaN','Infinity','1e3','1.001','0',True,200]:
            with self.subTest(value=value), self.assertRaises(Problem): amount_cents(value)
    def test_rules_use_word_boundaries(self):
        self.assertEqual(categorize('Internet bill'),'bills')
        self.assertEqual(categorize('Business meeting'),'other')
        self.assertEqual(categorize('Bolt ride'),'transport')
    def test_month_validation(self):
        with self.assertRaises(Problem): self.app.summary('2026-13')
    def test_formula_like_description_is_safe_on_export(self):
        self.app.add(dict(date='2026-10-01',description='@SUM(A1)',amount='1'))
        output=self.app.handle('GET','/api/export.csv',{'month':'2026-10'},{}).body.decode()
        self.assertIn("'@SUM",output)

if __name__=='__main__': unittest.main()
