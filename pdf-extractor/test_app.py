import unittest
from app import extract, validate

class ExtractionTests(unittest.TestCase):
    def test_signed_viewer_and_duplicates(self):
        source = '''<p>MCQ Practice Test 1 - Questions.pdf</p><iframe src="https://assets.teachablecdn.com/viewer?file=https%3A%2F%2Fuploads.teachablecdn.com%2Ftest.pdf%3FSignature%3Da%252Bb%26Expires%3D123"></iframe><a href="https://uploads.teachablecdn.com/test.pdf?Signature=a%2Bb&amp;Expires=123">download</a>'''
        files = extract(source, 'https://physicslab.app/lesson')
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['url'], 'https://uploads.teachablecdn.com/test.pdf?Signature=a%2Bb&Expires=123')
        self.assertEqual(files[0]['title'], 'MCQ Practice Test 1 - Questions.pdf')
        self.assertEqual(files[0]['kind'], 'Questions')
    def test_unrelated_embeds_ignored(self):
        self.assertEqual(extract('<iframe src="https://youtube.com/video"></iframe>', 'https://physicslab.app/'), [])
    def test_network_scope(self):
        for url in ('http://physicslab.app/', 'https://127.0.0.1/', 'https://physicslab.app.evil.com/', 'https://user@physicslab.app/', 'https://physicslab.app:8443/'):
            with self.assertRaises(ValueError):
                validate(url)
        validate('https://uploads.teachablecdn.com/example.pdf')

if __name__ == '__main__':
    unittest.main()
