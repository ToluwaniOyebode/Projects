import tempfile
import unittest
from pathlib import Path
from service import App
from search import chunks,tokenize
from webcore import Problem

class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=App(str(Path(self.tmp.name)/'search.db'),False)
    def tearDown(self):self.tmp.cleanup()
    def save(self,title,content):return self.app.save({'title':title,'content':content})
    def search(self,q,**query):return self.app.handle('GET','/api/search',{'q':q,**query},{})
    def test_rare_matching_term_outweighs_common_term(self):
        rare=self.save('A','# Guide\nSQLite transaction ledger')
        self.save('B','transaction monitoring logging')
        self.save('C','transaction pipeline retries')
        result=self.search('SQLite transaction')
        self.assertEqual(result['results'][0]['document_id'],rare['id'])
        self.assertEqual({x['term'] for x in result['results'][0]['explanation']},{'sqlite','transaction'})
    def test_all_mode_requires_every_term(self):
        self.save('A','inventory stock');self.save('B','inventory only')
        self.assertEqual(self.search('inventory stock',mode='all')['total'],1)
        self.assertEqual(self.search('inventory unknown',mode='all')['total'],0)
    def test_update_removes_stale_postings_atomically(self):
        row=self.save('Guide','oldterm')
        self.app.save({'title':'Guide','content':'newterm','version':1},row['id'])
        self.assertEqual(self.search('oldterm')['total'],0)
        self.assertEqual(self.search('newterm')['total'],1)
        with self.assertRaises(Problem):self.app.save({'title':'Guide','content':'wrong','version':1},row['id'])
        self.assertEqual(self.search('newterm')['total'],1)
    def test_delete_cascades_and_reopen_is_persistent(self):
        row=self.save('Guide','needle')
        self.assertEqual(App(self.app.path,False).handle('GET','/api/search',{'q':'needle'}, {})['total'],1)
        self.app.handle('DELETE',f"/api/documents/{row['id']}",{}, {})
        self.assertEqual(self.search('needle')['total'],0)
    def test_source_line_ranges_and_chunk_boundaries(self):
        parts=list(chunks('# Heading\nfirst source\nsecond source\n\n## Next\nlast source'))
        self.assertEqual((parts[0][0],parts[0][2],parts[0][3]),('Heading',2,3))
        self.assertEqual(parts[1][2],6)
        self.assertGreater(len(list(chunks(' '.join(['token']*250)))),1)
    def test_unicode_and_stopword_queries(self):
        self.save('Notes','café naïve 世界')
        self.assertEqual(self.search('CAFÉ')['total'],1)
        self.assertEqual(self.search('the and')['total'],0)
    def test_query_is_not_sql(self):
        self.save('Notes','sqlite')
        self.search("' OR 1=1; DROP TABLE documents;--")
        self.assertEqual(self.app.handle('GET','/api/stats',{}, {})['documents'],1)
    def test_invalid_mode_and_limit(self):
        for extra in [{'mode':'bad'},{'limit':'0'},{'limit':'abc'}]:
            with self.assertRaises((ValueError,Problem)):self.search('a',**extra)

if __name__=='__main__':unittest.main()
