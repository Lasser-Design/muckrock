"""
Tests for the organization application
"""

from django.contrib.auth.models import User
from django.test import TestCase

from muckrock.accounts.models import Profile
from muckrock.organization.models import Organization

from datetime import datetime
from mock import Mock, patch
import nose.tools
import stripe

class OrganizationURLTests(TestCase):
    """Test the views for the organization app"""

    def setUp(self):
        """Set up models for the organization"""
        owner = User.objects.create(
            username='TestOwner',
            password='testowner'
        )
        Organization.objects.create(
            name='Test Organization',
            slug='test-organization',
            owner=owner,
            date_update=datetime.now(),
        )

    def test_index(self):
        """The index should be OK"""
        response = self.client.get('/organization/')
        self.assertEqual(response.status_code, 200)

    def test_create(self):
        """Create should redirect"""
        response = self.client.get('/organization/create/')
        self.assertEqual(response.status_code, 302)

    def test_detail(self):
        """Detail page should be OK"""
        response = self.client.get('/organization/test-organization/')
        self.assertEqual(response.status_code, 200)

    def test_delete(self):
        """ordinary users should not be able to access the delete page, hence 404"""
        response = self.client.get('/organization/test-orgainzation/delete/')
        self.assertEqual(response.status_code, 404)

# Creates mock items for testing methods that involve Stripe
mock_customer = Mock()
MockCustomer = Mock()
MockCustomer.create.return_value = mock_customer
MockCustomer.retrieve.return_value = mock_customer
mock_plan = Mock()
mock_plan.amount = 45000
mock_plan.name = 'Test Organization Plan'
mock_plan.id = 'test-organization-org-plan'
MockPlan = Mock()
MockPlan.create.return_value = mock_plan
MockPlan.retrieve.return_value = mock_plan
# Substitutes mock items for Stripe items in each test
@patch('stripe.Customer', MockCustomer)
@patch('stripe.Plan', MockPlan)
class OrganizationPaymentTests(TestCase):
    """Test the methods that create and destroy payments and plans"""
    # pylint: disable=no-self-use

    def setUp(self):
        """Set up models for the organization"""
        owner = User.objects.create(
            username='TestOwner',
            password='testowner'
        )
        org = Organization.objects.create(
            name='Test Organization',
            slug='test-organization',
            owner=owner,
            date_update=datetime.now(),
        )
        Profile.objects.create(
            user=owner,
            acct_type='community',
            organization=org,
            date_update=datetime.now(),
        )

    def test_create_plan(self):
        """Should create a plan and assign a value to the org's stripe_id field"""
        org = Organization.objects.get(slug='test-organization')
        org.create_plan()
        nose.tools.assert_true(org.stripe_id)

    def test_delete_plan(self):
        """Should delete the org's plan and set stripe_id to None"""
        org = Organization.objects.get(slug='test-organization')
        org.create_plan()
        org.delete_plan()
        nose.tools.assert_false(org.stripe_id)

    def test_update_plan(self):
        """
        Should create an org plan at once price point, then update the org's
        plan to a new price point.
        """
        org = Organization.objects.get(slug='test-organization')
        org.create_plan()
        plan = stripe.Plan.retrieve(org.stripe_id)
        nose.tools.eq_(plan.amount, org.monthly_cost)
        org.monthly_cost = 15000
        mock_plan.amount = 15000
        org.update_plan()
        plan = stripe.Plan.retrieve(org.stripe_id)
        nose.tools.eq_(plan.amount, org.monthly_cost)

    @nose.tools.raises(ValueError)
    def test_double_create_plan(self):
        """Should return an error after trying to create a plan twice in a row"""
        org = Organization.objects.get(slug='test-organization')
        org.create_plan()
        org.create_plan()

    @nose.tools.raises(ValueError)
    def test_delete_nonexistant_plan(self):
        """Should return an error after trying to delete a plan that doesn't exist"""
        org = Organization.objects.get(slug='test-organization')
        org.delete_plan()

    @nose.tools.raises(ValueError)
    def test_update_nonexistant_plan(self):
        """Should return an error after tying to update a plan that doesn't exist"""
        org = Organization.objects.get(slug='test-organization')
        org.update_plan()

    def test_start_subscription(self):
        """
        Should subscribe owner to the organization's plan,
        set the org to active, and reduce pro owners to community accounts
        """
        org = Organization.objects.get(slug='test-organization')
        profile = org.owner.get_profile()
        profile.acct_type = 'pro'
        org.create_plan()
        org.start_subscription()
        # customer = org.owner.get_profile().customer()
        # test if subscription was activated
        nose.tools.eq_(profile.acct_type, 'community')
        nose.tools.assert_true(org.active)

    def test_pause_subscription(self):
        """Should cancel owner's subscription and set the org to inactive"""
        org = Organization.objects.get(slug='test-organization')
        org.create_plan()
        org.start_subscription()
        org.pause_subscription()
        # customer = org.owner.get_profile().customer()
        # test if subscription was paused
        nose.tools.assert_false(org.active)
