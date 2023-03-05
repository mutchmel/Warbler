"""Message View tests."""

# run these tests like:
#
#    FLASK_ENV=production python -m unittest test_message_views.py


import os
from unittest import TestCase

from models import db, connect_db, Message, User

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"


# Now we can import app

from app import app, CURR_USER_KEY

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()

# Don't have WTForms use CSRF at all, since it's a pain to test

app.config['WTF_CSRF_ENABLED'] = False


class MessageViewTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()

        self.client = app.test_client()

        self.testuser = User.signup(username="testuser",
                                    email="test@test.com",
                                    password="testuser",
                                    image_url=None)

        db.session.commit()

    def test_add_message(self):
        """Can use add a message?"""

        # Since we need to change the session to mimic logging in,
        # we need to use the changing-session trick:

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id

            # Now, that session setting is saved, so we can have
            # the rest of ours test

            resp = c.post("/messages/new", data={"text": "Hello"})

            # Make sure it redirects
            self.assertEqual(resp.status_code, 302)

            msg = Message.query.one()
            self.assertEqual(msg.text, "Hello")
    
    def test_add_message_no_user(self):
        """Does posting a new message function for non-users correctly?"""
        with self.client as c:

            resp = c.post("/messages/new", data={"text": "Hello"}, follow_redirects=True)
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Access unauthorized", html)

    def test_add_message_invalid_user(self):
        """Does posting a new message function for invalid-users correctly?"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = 1234567 # user does not exist

            resp = c.post("/messages/new", data={"text": "Hello"}, follow_redirects=True)
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 404)
            self.assertIn("Page not found", html)

    def test_new_message_form_authorized(self):
        """Does the new message form display to authorized users correctly?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id

            resp = c.get("/messages/new")
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)

            self.assertIn('<textarea', html)
            self.assertIn("What", html)
            self.assertIn("s happening?", html)
            self.assertIn("Add my message!", html)
    
    def test_new_message_form_no_user(self):
        """Does the new message form display to non-users correctly?"""

        with self.client as c:

            resp = c.get("/messages/new")
            self.assertEqual(resp.status_code, 302)      

            resp = c.get("/messages/new", follow_redirects=True)      
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)

            self.assertIn('Access unauthorized', html)

    def test_add_message_form_invalid_user(self):
        """Does the new message form display to non-users correctly?"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = 1234567 # user does not exist

            resp = c.get("/messages/new", follow_redirects=True)
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 404)

    def test_show_message_self(self):
        """Does message show route display correct info for own messages"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id

            new_message = Message(text='Hello', user_id=self.testuser.id)
            db.session.add(new_message)
            db.session.commit()

            resp = c.get(f'/messages/{new_message.id}')
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('Hello', html)
            self.assertIn('Delete', html)
            self.assertIn(f'<a href=/users/{self.testuser.id}>@{self.testuser.username}</a>', html)

    def test_show_message_other(self):
        """Does message show route display correct info for others' messages"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id

            new_user = User(username='testuser2', email='test2@test.com', password='testuser2')
            db.session.add(new_user)
            db.session.commit()
            new_message = Message(text='Goodbye', user_id=new_user.id)
            db.session.add(new_message)
            db.session.commit()

            resp = c.get(f'/messages/{new_message.id}')
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('Goodbye', html)
            self.assertNotIn('Delete', html)
            self.assertIn(f'<a href=/users/{new_user.id}>@{new_user.username}</a>', html)

    def test_show_invalid_message(self):
        """Does message show route display correct info an invalid message id?"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id
            
            resp = c.get('/messages/1234567')
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 404)

    def test_delete_message(self):
        """Does message delete route function correctly for author?"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id
            
            new_message = Message(text='Hello', user_id=self.testuser.id)
            db.session.add(new_message)
            db.session.commit()

            resp = c.post(f'/messages/{new_message.id}/delete', follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            msgs = Message.query.all()
            self.assertEqual(len(msgs), 0)

    def test_delete_message_no_user(self):
        """Does message delete route display correct info for non-user"""
        with self.client as c:

            new_message = Message(text='Hello', user_id=self.testuser.id)
            db.session.add(new_message)
            db.session.commit()

            resp = c.post(f'/messages/{new_message.id}/delete', follow_redirects=True)
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Access unauthorized", html)
            msgs = Message.query.all()
            self.assertEqual(len(msgs), 1)

    def test_delete_message_other(self):
        """Does message delete route display correct info for others' messages"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.testuser.id

            new_user = User(username='testuser2', email='test2@test.com', password='testuser2')
            db.session.add(new_user)
            db.session.commit()
            new_message = Message(text='Goodbye', user_id=new_user.id)
            db.session.add(new_message)
            db.session.commit()

            resp = c.post(f'/messages/{new_message.id}/delete', follow_redirects=True)
            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('Access Denied', html)
            msgs = Message.query.all()
            self.assertEqual(len(msgs), 1)
