"""
Tests for ABAC (Attribute-Based Access Control) - Phase 4.2

ABAC allows fine-grained access control based on attributes of:
- Users (e.g., department, clearance level)
- Resources (e.g., department, budget, status)
- Environment (e.g., IP address, time of day)
- Time (e.g., business hours, day of week)
"""
import pytest
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.models.condition import Condition, ConditionGroup, ConditionOperator
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.permission import EnterprisePermissionService
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine
from outlabs_auth.core.config import EnterpriseConfig


@pytest.fixture
async def database():
    """Create a test database connection"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["outlabs_auth_test_abac"]

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
        ]
    )

    # Clean up before tests
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await EntityModel.delete_all()
    await EntityMembershipModel.delete_all()
    await EntityClosureModel.delete_all()

    yield db

    # Clean up after tests
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await EntityModel.delete_all()
    await EntityMembershipModel.delete_all()
    await EntityClosureModel.delete_all()


@pytest.fixture
def config():
    """Create test configuration"""
    return EnterpriseConfig(
        secret_key="test-secret-key-12345",
        redis_enabled=False,
    )


@pytest.fixture
def policy_engine():
    """Create policy evaluation engine"""
    return PolicyEvaluationEngine()


# Unit Tests for PolicyEvaluationEngine


@pytest.mark.asyncio
async def test_policy_engine_equals_operator(policy_engine):
    """Test EQUALS operator"""
    condition = Condition(
        attribute="user.department",
        operator=ConditionOperator.EQUALS,
        value="engineering"
    )

    context = {
        "user": {"department": "engineering"}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["user"]["department"] = "sales"
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_less_than_operator(policy_engine):
    """Test LESS_THAN operator"""
    condition = Condition(
        attribute="resource.budget",
        operator=ConditionOperator.LESS_THAN,
        value=100000
    )

    context = {
        "resource": {"budget": 50000}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["resource"]["budget"] = 150000
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_in_operator(policy_engine):
    """Test IN operator"""
    condition = Condition(
        attribute="user.role",
        operator=ConditionOperator.IN,
        value=["manager", "director", "vp"]
    )

    context = {
        "user": {"role": "manager"}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["user"]["role"] = "intern"
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_contains_operator(policy_engine):
    """Test CONTAINS operator"""
    condition = Condition(
        attribute="user.tags",
        operator=ConditionOperator.CONTAINS,
        value="admin"
    )

    context = {
        "user": {"tags": ["admin", "developer", "reviewer"]}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["user"]["tags"] = ["developer", "reviewer"]
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_starts_with_operator(policy_engine):
    """Test STARTS_WITH operator"""
    condition = Condition(
        attribute="user.email",
        operator=ConditionOperator.STARTS_WITH,
        value="admin@"
    )

    context = {
        "user": {"email": "admin@example.com"}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["user"]["email"] = "user@example.com"
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_exists_operator(policy_engine):
    """Test EXISTS operator"""
    condition = Condition(
        attribute="user.clearance_level",
        operator=ConditionOperator.EXISTS
    )

    context = {
        "user": {"clearance_level": "secret"}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context = {"user": {}}
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_is_true_operator(policy_engine):
    """Test IS_TRUE operator"""
    condition = Condition(
        attribute="user.is_verified",
        operator=ConditionOperator.IS_TRUE
    )

    context = {
        "user": {"is_verified": True}
    }

    result = policy_engine.evaluate_condition(condition, context)
    assert result is True

    # Negative case
    context["user"]["is_verified"] = False
    result = policy_engine.evaluate_condition(condition, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_condition_group_and(policy_engine):
    """Test condition group with AND operator"""
    group = ConditionGroup(
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering"
            ),
            Condition(
                attribute="resource.department",
                operator=ConditionOperator.EQUALS,
                value="engineering"
            )
        ],
        operator="AND"
    )

    # Both conditions true
    context = {
        "user": {"department": "engineering"},
        "resource": {"department": "engineering"}
    }
    result = policy_engine.evaluate_condition_group(group, context)
    assert result is True

    # One condition false
    context["resource"]["department"] = "sales"
    result = policy_engine.evaluate_condition_group(group, context)
    assert result is False


@pytest.mark.asyncio
async def test_policy_engine_condition_group_or(policy_engine):
    """Test condition group with OR operator"""
    group = ConditionGroup(
        conditions=[
            Condition(
                attribute="user.role",
                operator=ConditionOperator.EQUALS,
                value="admin"
            ),
            Condition(
                attribute="user.role",
                operator=ConditionOperator.EQUALS,
                value="manager"
            )
        ],
        operator="OR"
    )

    # First condition true
    context = {"user": {"role": "admin"}}
    result = policy_engine.evaluate_condition_group(group, context)
    assert result is True

    # Second condition true
    context = {"user": {"role": "manager"}}
    result = policy_engine.evaluate_condition_group(group, context)
    assert result is True

    # Both false
    context = {"user": {"role": "user"}}
    result = policy_engine.evaluate_condition_group(group, context)
    assert result is False


# Integration Tests with EnterprisePermissionService


@pytest.fixture
async def test_user(database):
    """Create a test user with department attribute"""
    user = UserModel(
        email="abactest@example.com",
        hashed_password="test_hash",
        is_superuser=False,
        metadata={
            "department": "engineering"
        }
    )
    await user.save()
    return user


@pytest.fixture
async def entity_hierarchy(database, config):
    """Create a test entity hierarchy"""
    entity_service = EntityService(config=config, redis_client=None)

    # Create platform
    platform = await entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corp",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="platform",
    )

    # Create engineering department
    eng_dept = await entity_service.create_entity(
        name="engineering",
        display_name="Engineering Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(platform.id),
        metadata={"department": "engineering", "budget": 500000}
    )

    # Create sales department
    sales_dept = await entity_service.create_entity(
        name="sales",
        display_name="Sales Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(platform.id),
        metadata={"department": "sales", "budget": 300000}
    )

    return {
        "platform": platform,
        "eng_dept": eng_dept,
        "sales_dept": sales_dept,
    }


@pytest.mark.asyncio
async def test_abac_department_matching(database, config, test_user, entity_hierarchy):
    """Test ABAC with department matching condition"""
    # Create role with ABAC condition: user can only manage entities in same department
    role = RoleModel(
        name="dept_manager",
        display_name="Department Manager",
        permissions=["entity:update", "user:manage"],
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering",
                description="User must be in engineering department"
            )
        ]
    )
    await role.save()

    # Add user to engineering department with this role
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["eng_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # User should have permission in engineering dept (same department)
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["eng_dept"].id)
    )
    assert has_perm is True
    assert "abac" in source

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_budget_limit(database, config, test_user, entity_hierarchy):
    """Test ABAC with budget limit condition"""
    # Create role that only allows managing low-budget entities
    role = RoleModel(
        name="low_budget_manager",
        display_name="Low Budget Manager",
        permissions=["entity:update"],
        conditions=[
            Condition(
                attribute="resource.budget",
                operator=ConditionOperator.LESS_THAN,
                value=400000,
                description="Can only manage entities with budget < $400k"
            )
        ]
    )
    await role.save()

    # Add user to both departments
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["sales_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # User should have permission in sales dept (budget = $300k < $400k)
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["sales_dept"].id)
    )
    assert has_perm is True
    assert "abac" in source

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_condition_denied(database, config, test_user, entity_hierarchy):
    """Test ABAC condition denial"""
    # Create role with condition that will fail
    role = RoleModel(
        name="restricted_manager",
        display_name="Restricted Manager",
        permissions=["entity:update"],
        conditions=[
            Condition(
                attribute="resource.budget",
                operator=ConditionOperator.GREATER_THAN,
                value=1000000,  # Very high threshold
                description="Can only manage high-budget entities"
            )
        ]
    )
    await role.save()

    # Add user to engineering department
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["eng_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # User should NOT have permission (budget = $500k < $1M)
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["eng_dept"].id)
    )
    assert has_perm is False
    assert source == "abac_denied"

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_multiple_conditions(database, config, test_user, entity_hierarchy):
    """Test ABAC with multiple conditions (AND logic)"""
    # Create role with multiple conditions
    role = RoleModel(
        name="multi_condition_manager",
        display_name="Multi-Condition Manager",
        permissions=["entity:update"],
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering"
            ),
            Condition(
                attribute="resource.budget",
                operator=ConditionOperator.LESS_THAN,
                value=600000
            )
        ]
    )
    await role.save()

    # Add user to engineering department
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["eng_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Both conditions should pass
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["eng_dept"].id)
    )
    assert has_perm is True
    assert "abac" in source

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_condition_groups_or(database, config, test_user, entity_hierarchy):
    """Test ABAC with condition groups using OR logic"""
    # Create role with OR condition group
    role = RoleModel(
        name="or_condition_manager",
        display_name="OR Condition Manager",
        permissions=["entity:update"],
        condition_groups=[
            ConditionGroup(
                conditions=[
                    Condition(
                        attribute="user.department",
                        operator=ConditionOperator.EQUALS,
                        value="sales"
                    ),
                    Condition(
                        attribute="resource.budget",
                        operator=ConditionOperator.LESS_THAN,
                        value=400000
                    )
                ],
                operator="OR"
            )
        ]
    )
    await role.save()

    # Add user to sales department
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["sales_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Second condition should pass (budget $300k < $400k)
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["sales_dept"].id)
    )
    assert has_perm is True
    assert "abac" in source

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_with_custom_context(database, config, test_user, entity_hierarchy):
    """Test ABAC with custom context provided"""
    # Create role with condition
    role = RoleModel(
        name="custom_context_manager",
        display_name="Custom Context Manager",
        permissions=["entity:update"],
        conditions=[
            Condition(
                attribute="env.ip_range",
                operator=ConditionOperator.STARTS_WITH,
                value="10.0.0."
            )
        ]
    )
    await role.save()

    # Add user to engineering department
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["eng_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Provide custom context with IP address
    custom_context = {
        "user": {"department": "engineering"},
        "resource": {"budget": 500000, "department": "engineering"},
        "env": {"ip_range": "10.0.0.100"},
        "time": {"hour": 14}
    }

    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["eng_dept"].id),
        context=custom_context
    )
    assert has_perm is True
    assert "abac" in source

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_abac_role_without_conditions_passes(database, config, test_user, entity_hierarchy):
    """Test that roles without conditions work normally"""
    # Create role WITHOUT conditions
    role = RoleModel(
        name="normal_manager",
        display_name="Normal Manager",
        permissions=["entity:update"]
        # No conditions
    )
    await role.save()

    # Add user to engineering department
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["eng_dept"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Should work normally (no ABAC checks)
    has_perm, source = await perm_service.check_permission_with_context(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["eng_dept"].id)
    )
    assert has_perm is True
    # Source should be "direct" not "abac" since no conditions
    assert source == "direct"

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_build_context_from_models(database, config, test_user, entity_hierarchy):
    """Test building ABAC context from database models"""
    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    context = await perm_service.build_context_from_models(
        str(test_user.id),
        str(entity_hierarchy["eng_dept"].id)
    )

    # Verify user context
    assert "user" in context
    assert context["user"]["email"] == "abactest@example.com"
    assert context["user"]["department"] == "engineering"

    # Verify resource context
    assert "resource" in context
    assert context["resource"]["name"] == "engineering"
    assert context["resource"]["budget"] == 500000

    # Verify time context (auto-generated)
    assert "time" in context
    assert "hour" in context["time"]
    assert "is_business_hours" in context["time"]
