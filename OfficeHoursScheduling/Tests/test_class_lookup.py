from django.test import TestCase


class ClassLookupTests(TestCase):
    def setUp(self):
        Course.objects.create(course_code='CS361')
        
    def test_class_lookup_page_loads(self):
        response = self.client.get('/classes/')

        self.assertEqual(response.status_code, 200)

    def test_class_lookup_empty_search(self):
        response = self.client.get('/classes/', {'course': ''})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a course')
        
    def test_class_lookup_valid_class(self):
        response = self.client.get('/classes/', {'course': 'CS361'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CS361')

    def test_class_lookup_invalid_class(self):
        response = self.client.get('/classes/', {'course': 'INVALID123'})
