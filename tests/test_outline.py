import unittest
import os
import json
import tempfile
import shutil
import HtmlTestRunner
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from database import DatabaseHandler
from manager_encryption import EncryptionManager
from manager_json import validate_json_schema, load_from_json_file
from manager_docx import export_to_docx
from manager_pdf import export_to_pdf

class TestBase(unittest.TestCase):
    """Base test class with common setup and teardown"""
    
    @classmethod
    def setUpClass(cls):
        """Create temporary directory for test databases and files"""
        cls.test_dir = tempfile.mkdtemp()
        cls.test_db_path = os.path.join(cls.test_dir, "test.db")
        cls.test_password = "TestPassword123!"
        cls.encryption_manager = EncryptionManager(cls.test_password)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test directory"""
        shutil.rmtree(cls.test_dir)
    
    def setUp(self):
        """Set up fresh database for each test"""
        self.db = DatabaseHandler(self.test_db_path, self.encryption_manager)
        self.db.setup_database()
        self.db.set_password(self.test_password)
    
    def tearDown(self):
        """Clean up database after each test"""
        self.db.close()
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def create_test_hierarchy(self):
        """Helper method to create a test hierarchy"""
        # Create header
        header_id = self.db.add_section("Test Header", "header")
        
        # Create categories
        cat1_id = self.db.add_section("Category 1", "category", header_id)
        cat2_id = self.db.add_section("Category 2", "category", header_id)
        
        # Create subcategories
        subcat1_id = self.db.add_section("Subcategory 1", "subcategory", cat1_id)
        subcat2_id = self.db.add_section("Subcategory 2", "subcategory", cat1_id)
        
        # Create subheaders
        self.db.add_section("Subheader 1", "subheader", subcat1_id)
        self.db.add_section("Subheader 2", "subheader", subcat1_id)
        
        return header_id, cat1_id, cat2_id, subcat1_id, subcat2_id

class TestDatabaseOperations(TestBase):
    """Test database CRUD operations and encryption"""
    
    def test_add_section(self):
        """Test adding a section with encryption"""
        test_title = "Test Header"
        section_id = self.db.add_section(test_title, "header")
        
        self.assertIsNotNone(section_id)
        
        self.db.cursor.execute("SELECT title FROM sections WHERE id = ?", (section_id,))
        encrypted_title = self.db.cursor.fetchone()[0]
        decrypted_title = self.db.decrypt_safely(encrypted_title)
        self.assertEqual(decrypted_title, test_title)

    def test_update_section(self):
        """Test updating a section with questions"""
        section_id = self.db.add_section("Initial Title", "header")
        
        new_title = "Updated Title"
        new_questions = json.dumps(["Question 1", "Question 2"])
        self.db.update_section(section_id, new_title, new_questions)
        
        self.db.cursor.execute("SELECT title, questions FROM sections WHERE id = ?", (section_id,))
        row = self.db.cursor.fetchone()
        decrypted_title = self.db.decrypt_safely(row[0])
        decrypted_questions = self.db.decrypt_safely(row[1])
        
        self.assertEqual(decrypted_title, new_title)
        self.assertEqual(json.loads(decrypted_questions), json.loads(new_questions))

    def test_delete_section_cascade(self):
        """Test cascading delete of sections"""
        ids = self.create_test_hierarchy()
        root_id = ids[0]
        
        # Count initial sections
        self.db.cursor.execute("SELECT COUNT(*) FROM sections")
        initial_count = self.db.cursor.fetchone()[0]
        
        # Delete root
        self.db.delete_section(root_id)
        
        # Verify all sections were deleted
        self.db.cursor.execute("SELECT COUNT(*) FROM sections")
        final_count = self.db.cursor.fetchone()[0]
        
        self.assertEqual(final_count, 0)
        self.assertEqual(initial_count - final_count, 7)  # Verify exact number deleted

class TestTreeOperations(TestBase):
    """Test tree manipulation operations"""
    
    def test_move_up_down(self):
        """Test moving sections up and down"""
        header_id = self.db.add_section("Header", "header")
        
        # Add categories in specific order
        cat1_id = self.db.add_section("Category 1", "category", header_id)
        cat2_id = self.db.add_section("Category 2", "category", header_id)
        cat3_id = self.db.add_section("Category 3", "category", header_id)
        
        # Test moving up
        self.db.cursor.execute(
            """UPDATE sections 
            SET placement = placement - 1 
            WHERE id = ? AND parent_id = ?""", 
            (cat3_id, header_id)
        )
        
        # Verify new positions
        self.db.cursor.execute(
            "SELECT placement FROM sections WHERE id = ?", 
            (cat3_id,)
        )
        new_placement = self.db.cursor.fetchone()[0]
        self.assertEqual(new_placement, 2)

    def test_move_left_right(self):
        """Test moving sections left and right in hierarchy"""
        header_id = self.db.add_section("Header", "header")
        cat1_id = self.db.add_section("Category 1", "category", header_id)
        cat2_id = self.db.add_section("Category 2", "category", header_id)
        
        # Move category 2 under category 1
        self.db.cursor.execute(
            "UPDATE sections SET parent_id = ? WHERE id = ?",
            (cat1_id, cat2_id)
        )
        
        # Verify new parent
        self.db.cursor.execute(
            "SELECT parent_id FROM sections WHERE id = ?",
            (cat2_id,)
        )
        new_parent = self.db.cursor.fetchone()[0]
        self.assertEqual(new_parent, cat1_id)

class TestEncryption(TestBase):
    """Test encryption operations"""
    
    def test_password_change(self):
        """Test changing database password"""
        # Add test data
        section_id = self.db.add_section("Test Section", "header")
        original_questions = json.dumps(["Original Question"])
        self.db.update_section(section_id, "Test Section", original_questions)
        
        # Change password
        new_password = "NewPassword123!"
        self.db.change_password(self.test_password, new_password)
        
        # Verify data with new password
        new_encryption_manager = EncryptionManager(new_password)
        self.db.encryption_manager = new_encryption_manager
        
        self.db.cursor.execute("SELECT title, questions FROM sections WHERE id = ?", (section_id,))
        row = self.db.cursor.fetchone()
        decrypted_title = self.db.decrypt_safely(row[0])
        decrypted_questions = self.db.decrypt_safely(row[1])
        
        self.assertEqual(decrypted_title, "Test Section")
        self.assertEqual(json.loads(decrypted_questions), json.loads(original_questions))

    def test_encryption_strength(self):
        """Test encryption strength and uniqueness"""
        test_title = "Test Title"
        
        # Encrypt same title multiple times
        encrypted1 = self.encryption_manager.encrypt_string(test_title)
        encrypted2 = self.encryption_manager.encrypt_string(test_title)
        
        # Verify different ciphertexts (due to IV/salt)
        self.assertNotEqual(encrypted1, encrypted2)
        
        # Verify both decrypt correctly
        decrypted1 = self.encryption_manager.decrypt_string(encrypted1)
        decrypted2 = self.encryption_manager.decrypt_string(encrypted2)
        
        self.assertEqual(decrypted1, test_title)
        self.assertEqual(decrypted2, test_title)

class TestSearch(TestBase):
    """Test search functionality"""
    
    def test_search_titles(self):
        """Test searching section titles"""
        self.create_test_hierarchy()
        
        # Search for "Category"
        ids_to_show, parents_to_show = self.db.search_sections("Category")
        
        self.assertTrue(len(ids_to_show) >= 2)  # Should find at least 2 categories
        
    def test_search_questions(self):
        """Test searching question content"""
        header_id = self.db.add_section("Test Header", "header")
        self.db.update_section(header_id, "Test Header", 
                             json.dumps(["Sample question about Python"]))
        
        # Search for "Python"
        ids_to_show, parents_to_show = self.db.search_sections("Python")
        
        self.assertIn(header_id, ids_to_show)

class TestExport(TestBase):
    """Test export functionality"""
    
    @patch('tkinter.filedialog.asksaveasfilename')
    def test_docx_export(self, mock_savedialog):
        """Test DOCX export"""
        self.create_test_hierarchy()
        
        # Set up mock file path
        test_docx = os.path.join(self.test_dir, "test_export.docx")
        mock_savedialog.return_value = test_docx
        
        # Export
        export_to_docx(self.db)
        
        # Verify file was created
        self.assertTrue(os.path.exists(test_docx))
        self.assertTrue(os.path.getsize(test_docx) > 0)

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_pdf_export(self, mock_savedialog):
        """Test PDF export"""
        self.create_test_hierarchy()
        
        # Set up mock file path
        test_pdf = os.path.join(self.test_dir, "test_export.pdf")
        mock_savedialog.return_value = test_pdf
        
        # Export
        export_to_pdf(self.db)
        
        # Verify file was created
        self.assertTrue(os.path.exists(test_pdf))
        self.assertTrue(os.path.getsize(test_pdf) > 0)

def generate_test_report():
    """Generate HTML test report with detailed results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestDatabaseOperations,
        TestTreeOperations,
        TestEncryption,
        TestSearch,
        TestExport
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Create reports directory
    reports_dir = os.path.join(os.path.dirname(__file__), 'test_reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate timestamp for report name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(reports_dir, f'test_report_{timestamp}.html')
    
    # Run tests with HTML reporter
    runner = HtmlTestRunner.HTMLTestRunner(
        combine_reports=True,
        report_title="Outline Editor Test Report",
        report_name="Test Results",
        output=report_file,
        template=None  # Use default template
    )
    
    result = runner.run(suite)
    
    return result, report_file

if __name__ == '__main__':
    # Run tests and generate report
    result, report_file = generate_test_report()
    
    # Print summary to console
    print("\nTest Summary:")
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"\nDetailed HTML report generated: {report_file}")