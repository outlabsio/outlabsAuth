#!/usr/bin/env python3
"""
Debug entity visibility issue
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core.db import init_db
from api.services.entity_service import EntityService
from beanie import PydanticObjectId
from api.config import get_settings


async def debug_user_visible_entities():
    """Debug the get_user_visible_entities function"""
    # Initialize database
    settings = get_settings()
    await init_db(settings)
    
    # Test user ID from the previous test
    user_id = "687ea4d5d974a0042384f87f"
    
    print(f"\nDebugging visibility for user: {user_id}")
    
    # Get visible entities
    visible_entity_ids = await EntityService.get_user_visible_entities(
        user_id,
        include_tree_permissions=True
    )
    
    print(f"\nVisible entity IDs: {visible_entity_ids}")
    print(f"Total visible entities: {len(visible_entity_ids)}")
    
    # Let's also check memberships directly
    from api.models import EntityMembershipModel
    
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == PydanticObjectId(user_id),
        EntityMembershipModel.status == "active"
    ).to_list()
    
    print(f"\nFound {len(memberships)} memberships")
    
    for membership in memberships:
        print(f"\nMembership ID: {membership.id}")
        print(f"Entity link type: {type(membership.entity)}")
        print(f"Has fetch: {hasattr(membership.entity, 'fetch')}")
        
        if hasattr(membership.entity, 'fetch'):
            entity = await membership.entity.fetch()
            if entity:
                print(f"Fetched entity ID: {entity.id}")
                print(f"Entity name: {entity.name}")
        else:
            print(f"Entity value: {membership.entity}")


if __name__ == "__main__":
    asyncio.run(debug_user_visible_entities())