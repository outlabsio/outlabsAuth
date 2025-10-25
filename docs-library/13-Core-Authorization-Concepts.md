# 13. Core Authorization Concepts

This document explains the core concepts of the OutlabsAuth authorization model, including the relationships between Users, Permissions, Roles, and Entities.

## The Core Components

At its heart, the system uses a Role-Based Access Control (RBAC) model.

1.  **Permission**: A single, specific action a user can perform. These are represented as strings, typically in the format `resource:action` (e.g., `user:create`, `invoice:approve`).
2.  **Role**: A named collection of permissions. For example, an "Accountant" role might contain the `invoice:read`, `invoice:create`, and `invoice:pay` permissions. Roles are the primary way to manage and assign permissions.
3.  **User**: An actor in the system who is granted roles.

The standard flow of permissions is straightforward: Permissions are grouped into Roles, and Roles are assigned to Users.

## The Two Models: Simple vs. Enterprise

OutlabsAuth offers two primary presets that determine how these components are structured.

### 1. The `SimpleRBAC` Structure

This model is designed for applications that do not need a complex organizational hierarchy. It answers the question: **Who can do What?**

In this model, a `User` is directly linked to one or more `Roles` through a membership table.

**Diagram:**
```
           ┌──────────────┐
           │  Permission  │
           │ "user:read"  │
           └──────┬───────┘
                  │ (is part of)
           ┌──────▼───────┐
           │     Role     │
           │   "Viewer"   │
           └──────┬───────┘
                  │ (is assigned via UserRoleMembership)
           ┌──────▼───────┐
           │     User     │
           │"john@doe.com"│
           └──────────────┘
```
A user's total permissions are the sum of all permissions from all the roles they are assigned.

### 2. The `EnterpriseRBAC` Structure

This model introduces the **Entity** as a fourth component, creating a powerful hierarchical system. It answers the question: **Who can do What, and Where?**

*   **Entity**: Represents a context, such as a company, a department, a project, or a team. Entities can be nested to form a hierarchy.

In this model, a role is not assigned directly to a user. Instead, a user is assigned a role *within the context of an entity*.

**Diagram:**
```
           ┌──────────────┐         ┌──────────────┐
           │  Permission  │         │    Entity    │
           │ "user:manage"│         │ "Eng. Dept"  │
           └──────┬───────┘         └──────┬───────┘
                  │ (is part of)           │
           ┌──────▼───────┐                │
           │     Role     │                │
           │  "Manager"   │                │
           └──────┬───────┘                │
                  │                        │
                  └──────────┬─────────────┘
                             │ (is assigned to user *in* entity via EntityMembership)
                      ┌──────▼───────┐
                      │     User     │
                      │"jane@doe.com"│
                      └──────────────┘
```
Here, "jane@doe.com" is only a "Manager" *within the "Eng. Dept" entity*. Her permissions from that role only apply when she is performing actions related to that department or its children (if using tree permissions).

---

## Understanding Entities: Structural vs. Access Groups

The `EnterpriseRBAC` model has two types of entities, which provides immense flexibility.

### `STRUCTURAL` Entities

Think of these as the formal, rigid organizational chart. They define **"where you work"** and are used to build the main hierarchy.

*   **Example**: `Company > Division > Department > Team`

### `ACCESS_GROUP` Entities (Non-Structural)

Think of these as flexible "tags" or "labels" that grant permissions **across** the formal org chart. They define **"what you're working on"**.

This is best explained with a use case.

#### Use Case: The Cross-Functional Project Team

Imagine your `STRUCTURAL` hierarchy is `ACME Corp > Finance | Engineering | Marketing`.

A new project, **"Project Phoenix,"** requires Alice from Finance, Bob from Engineering, and Carol from Marketing to collaborate. They all need special permissions, like `phoenix:edit_document`, but only for this project.

Instead of creating messy, temporary roles in each department, you create a single `ACCESS_GROUP` entity called **"Project Phoenix Team"**.

1.  You create a project-specific role, **"Phoenix Contributor,"** with the needed permissions.
2.  You make Alice, Bob, and Carol members of the "Project Phoenix Team" group with the "Phoenix Contributor" role.

Now, each user has two memberships:
*   **Bob:** Is a member of "Engineering" (his structural home) AND "Project Phoenix Team" (his temporary access group).

**Diagram:**
```
              ACME Corp (STRUCTURAL)
              ┌─────┴─────┐
              │           │
      Finance (STRUCTURAL)   Engineering (STRUCTURAL)
          │                       │
        Alice (User)             Bob (User)
          │                       │
          └─────────┐   ┌─────────┘
                    │   │
           ┌────────▼───▼────────┐
           │ "Project Phoenix"   │  <-- ACCESS_GROUP
           │ (Non-Structural)    │
           └─────────────────────┘
```

### How Permissions Are Resolved

When the system checks a user's permissions, it aggregates them from **all of their memberships**.

Bob gets his day-to-day permissions from his role in the "Engineering" department, **PLUS** his project-specific permissions from his role in the "Project Phoenix Team" access group.

This design allows you to grant temporary or project-based permissions cleanly and securely, without disrupting the primary organizational hierarchy. When the project ends, you simply delete the access group or remove the memberships, and the special access is instantly revoked.

---

### The Flexibility of Entities: Custom Types and Infinite Depth

Beyond the `STRUCTURAL` vs. `ACCESS_GROUP` distinction, two other features make the entity system exceptionally powerful and adaptable.

#### 1. User-Defined Entity Types (No Enums)

Most authorization systems force you into their predefined terminology (e.g., you must use the word "Team" or "Group"). This system smartly avoids this by making the `entity_type` a flexible string.

**Why this is powerful:**
This allows the system to adopt the language of any business domain, making it more intuitive for the end-users.
*   A **software company** can use types like `"Division"`, `"Squad"`, and `"Guild"`.
*   A **real estate agency** can use `"Region"`, `"Office"`, and `"Agent Team"`.
*   A **hospital** can use `"Campus"`, `"Ward"`, and `"Care Team"`.

The library doesn't need to be changed; it simply adapts to the organization's own vocabulary.

**The Challenge of Flexibility:** This freedom can lead to inconsistency (e.g., one admin uses `"department"` while another uses `"Dept"`).

**The Recommended Solution (Frontend Guidance):**
The best practice is to have the frontend guide users toward consistency. When an admin creates a new entity, the UI can fetch all distinct, existing `entity_type` names and suggest them in a dropdown or autocomplete field. This provides the best of both worlds:
*   **Backend Flexibility:** The database allows any string.
*   **Frontend Guidance:** The UI encourages normalization and consistency.

#### 2. Infinite Hierarchy and Performance

The design does not impose an artificial limit on how deep the `STRUCTURAL` hierarchy can be. An organization can have 3 levels or 30.

**The Performance Secret (The Closure Table):**
An "infinite" hierarchy would normally be a performance nightmare, requiring slow, recursive database queries to check permissions.

However, this system is built for this kind of scale. It uses a **Closure Table** (`EntityClosureModel`) to pre-calculate all ancestor-descendant relationships. This means that checking permissions on a deeply nested entity is still a single, lightning-fast `O(1)` database query.

This design choice allows the system to offer unlimited flexibility in its data model because it is supported by a highly scalable and professional technical implementation.