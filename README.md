# Subscription Management System

A unified platform for managing products, subscription plans,
quotations, recurring invoices, payments, and financial reporting.

> **Project scenario:** Brightloop Software\
> This README describes the proposed system workflow and the
> responsibilities of the four development modules. It is the team's
> shared reference for implementation and integration.

------------------------------------------------------------------------

## Table of Contents

1.  [Project Overview](#1-project-overview)
2.  [User Roles](#2-user-roles)
3.  [Overall System Workflow](#3-overall-system-workflow)
4.  [Invoice and Payment Workflow](#4-invoice-and-payment-workflow)
5.  [Four-Module Integration](#5-four-module-integration)
6.  [Module 4 Internal Architecture](#6-module-4-internal-architecture)
7.  [Conceptual Database
    Relationships](#7-conceptual-database-relationships)
8.  [Module Responsibilities](#8-module-responsibilities)
9.  [Business Rules and Integration
    Contracts](#9-business-rules-and-integration-contracts)
10. [Development and Git Workflow](#10-development-and-git-workflow)
11. [Testing Checklist](#11-testing-checklist)
12. [Setup Instructions](#12-setup-instructions)

------------------------------------------------------------------------

## 1. Project Overview

The Subscription Management System manages the full lifecycle of a
subscription business:

-   Customer registration and account access.
-   Product and subscription plan configuration.
-   Product variants, taxes, and discounts.
-   Quotations and subscription creation.
-   Recurring invoice generation.
-   Payment recording and outstanding balance tracking.
-   Financial dashboards and reports.

The system is intended to replace manual spreadsheet tracking, manually
prepared invoices, and manually reconciled payments.

### Main system goals

-   Reduce missed renewals and billing errors.
-   Prevent duplicate invoices and duplicate payment records.
-   Keep subscription, invoice, and payment information consistent.
-   Give customers access only to their own subscriptions and invoices.
-   Give authorized staff and administrators the tools required for
    daily operations.
-   Make financial information available through searchable reports and
    dashboards.
-   Keep pages responsive with thousands of subscription records; the
    project brief specifies a target of under two seconds.

------------------------------------------------------------------------

## 2. User Roles

  -----------------------------------------------------------------------
  Role                                Main responsibilities
  ----------------------------------- -----------------------------------
  Admin                               Manage the system, staff accounts,
                                      products, plans, taxes, and
                                      discount rules; access financial
                                      information.

  Internal Staff                      Handle permitted customer,
                                      quotation, subscription, invoice,
                                      and payment operations.

  Customer                            Access and manage their own
                                      account, subscriptions, and
                                      invoices through the customer
                                      portal.
  -----------------------------------------------------------------------

**Access rule:** Only an admin can create staff accounts. Backend
authorization must enforce role permissions; hiding a button in the
frontend is not sufficient.

------------------------------------------------------------------------

## 3. Overall System Workflow

This diagram shows the main journey from customer registration to
billing and financial reporting.

``` mermaid
flowchart TD
    A([Start]) --> B[Customer Registration]
    B --> C[Authentication]
    C --> D{User Role}

    D -->|Admin| E[Admin Dashboard]
    D -->|Staff| F[Staff Dashboard]
    D -->|Customer| G[Customer Portal]

    E --> H[Manage Products]
    H --> I[Configure Plans]
    I --> J[Configure Taxes and Discounts]

    F --> K[Create Quotation]
    K --> L[Select Customer, Plan and Products]
    L --> M[Create Subscription]

    M --> N[Subscription Lifecycle]
    N --> O{Subscription Status}

    O -->|Draft| P[Quotation]
    P --> Q[Confirmed]
    Q --> R[Active Subscription]

    R --> S[Billing Date Reached]
    S --> T[Generate Invoice Automatically]
    T --> U[Apply Taxes and Discounts]
    U --> V[Confirm Invoice]

    V --> W[Record Payment]
    W --> X{Payment Complete?}

    X -->|No| Y[Track Outstanding Balance]
    Y --> Z[Monitor Due Date]
    Z --> AA[Overdue Tracking]

    X -->|Yes| AB[Mark Invoice as Paid]

    AB --> AC[Financial Dashboard]
    AA --> AC
    Y --> AC

    AC --> AD[Revenue Reports]
    AC --> AE[Payment Reports]
    AC --> AF[Active Subscription Statistics]
    AC --> AG[Outstanding Invoice Reports]

    R --> AH{Renewal or Closure}
    AH -->|Renew| R
    AH -->|Close| AI([Closed Subscription])
```

### Workflow notes

-   A customer registers and authenticates before accessing protected
    features.
-   Admins configure products, plans, tax rules, and discount rules.
-   Staff prepare quotations and convert accepted quotations into
    subscriptions.
-   Active subscriptions become eligible for recurring billing according
    to their billing schedule.
-   The billing process creates an invoice, applies the relevant pricing
    rules, and makes it available for confirmation and sending.
-   Payments are recorded against invoices.
-   Outstanding and overdue balances are reflected in financial views.
-   Subscription renewal and closure are controlled by the subscription
    lifecycle rules.

------------------------------------------------------------------------

## 4. Invoice and Payment Workflow

This is the detailed workflow for **Module 4: Invoices, Payments &
Reports**.

``` mermaid
flowchart TD
    A[Active Subscription] --> B{Billing Date Reached?}

    B -->|No| C[Wait Until Next Billing Date]
    C --> B

    B -->|Yes| D[Check Previous Billing Records]

    D --> E{Invoice Already Exists for This Cycle?}
    E -->|Yes| F[Skip Duplicate Generation]
    E -->|No| G[Create Invoice]

    G --> H[Fetch Customer Details]
    H --> I[Fetch Subscription Product Lines]
    I --> J[Calculate Subtotal]
    J --> K[Apply Eligible Discounts]
    K --> L[Calculate Applicable Taxes]
    L --> M[Calculate Final Amount]

    M --> N[Save Invoice as Draft]
    N --> O[Confirm Invoice]
    O --> P[Send or Make Invoice Available to Customer]

    P --> Q[Receive Payment]
    Q --> R[Validate and Record Payment]
    R --> S[Link Payment to Invoice]
    S --> T[Recalculate Outstanding Balance]

    T --> U{Outstanding Balance Is Zero?}

    U -->|Yes| V[Mark Invoice as Paid]
    U -->|No| W[Keep Invoice Outstanding]

    W --> X{Due Date Passed?}
    X -->|Yes| Y[Flag Invoice as Overdue]
    X -->|No| Z[Wait for Additional Payment]

    Z --> Q
    Y --> Q

    V --> AA[Update Financial Dashboard]
    Y --> AA
    W --> AA

    AA --> AB[Update Revenue Reports]
    AA --> AC[Update Payment Reports]
    AA --> AD[Update Outstanding Reports]
```

### Invoice and payment rules

1.  An invoice must be generated from the relevant subscription and
    billing cycle.
2.  Invoice generation must be idempotent: retrying the same billing
    operation must not create another invoice for the same subscription
    and cycle.
3.  Invoice totals must be calculated consistently using the agreed tax
    and discount rules.
4.  A payment must reference the invoice it pays.
5.  If partial payments are supported, multiple payment records may be
    linked to one invoice.
6.  Outstanding balance is calculated as the invoice amount minus valid
    payments and any explicitly supported adjustments.
7.  An invoice is fully paid only when its outstanding balance is zero.
8.  An invoice with a positive outstanding balance becomes overdue when
    its due date has passed, subject to the agreed cancellation and
    status rules.
9.  Cancelled invoices must not be counted as collected revenue.
10. Payment retries must not create duplicate payment records. Use a
    unique payment reference or idempotency key where available.

> **Status design note:** The project brief lists Draft, Confirmed, and
> Paid as invoice statuses. Partial payment and overdue are useful
> financial conditions. The team should decide whether these are
> additional persisted statuses or derived display states, and document
> that decision consistently.

------------------------------------------------------------------------

## 5. Four-Module Integration

The four modules are developed separately but share data and depend on
one another.

``` mermaid
flowchart TB
    M1["MODULE 1<br/>Authentication and Customers"]
    M2["MODULE 2<br/>Products, Plans, Taxes and Discounts"]
    M3["MODULE 3<br/>Quotations and Subscriptions"]
    M4["MODULE 4<br/>Invoices, Payments and Reports"]

    M1 -->|Customer IDs and user roles| M3
    M1 -->|Access permissions| M4

    M2 -->|Product and plan details| M3
    M2 -->|Tax and discount rules| M4

    M3 -->|Confirmed active subscriptions and billing data| M4

    M4 -->|Invoice, payment and balance summaries| DASH["Financial Dashboard"]
    M3 -->|Subscription statistics| DASH

    DASH --> REPORTS["Revenue, Payment and Overdue Reports"]
```

### Integration dependencies

  -----------------------------------------------------------------------
  Module                  Provides                Used by
  ----------------------- ----------------------- -----------------------
  Module 1:               User IDs, customer IDs, Modules 3 and 4
  Authentication &        roles, access           
  Customers               permissions             

  Module 2: Products,     Product, variant, plan, Modules 3 and 4
  Plans, Taxes &          tax, and discount data  
  Discounts                                       

  Module 3: Quotations &  Subscription ID,        Module 4
  Subscriptions           customer, billing       
                          dates, subscription     
                          lines, lifecycle status 

  Module 4: Invoices,     Invoice records,        Dashboard and
  Payments & Reports      payment records,        customer/staff views
                          balances, financial     
                          summaries               
  -----------------------------------------------------------------------

### Integration sequence

1.  Agree on shared identifiers and database relationships.
2.  Module 1 establishes users, customers, and role permissions.
3.  Module 2 establishes products, plans, taxes, and discount rules.
4.  Module 3 uses customer and product data to create subscriptions.
5.  Module 4 consumes eligible subscription data to generate invoices
    and record payments.
6.  The dashboard and reports read consistent data from the shared
    database or documented APIs.

------------------------------------------------------------------------

## 6. Module 4 Internal Architecture

Module 4 contains three major areas: invoice management, payment
management, and financial reporting.

``` mermaid
flowchart TD
    A["MODULE 4"] --> B["Invoice Management"]
    A --> C["Payment Management"]
    A --> D["Financial Reporting"]

    B --> E["Invoice Generation"]
    B --> F["Invoice Calculation"]
    B --> G["Invoice Status and Actions"]
    B --> H["PDF and Printing"]

    C --> I["Record Payment"]
    C --> J["Payment Validation"]
    C --> K["Invoice-Payment Mapping"]
    C --> L["Outstanding Balance"]

    D --> M["Revenue Summary"]
    D --> N["Payment Summary"]
    D --> O["Overdue Invoices"]
    D --> P["Active Subscription Statistics"]

    E --> Q[("Shared Database")]
    F --> Q
    G --> Q
    I --> Q
    J --> Q
    K --> Q
    L --> Q

    Q --> R["Dashboard / Reporting API"]
    R --> S["Admin and Finance Dashboard"]
    R --> T["Reports, Filters and Exports"]
```

### Module 4 functional areas

  -----------------------------------------------------------------------
  Area                                Responsibilities
  ----------------------------------- -----------------------------------
  Invoice Management                  Generate invoices, calculate
                                      totals, manage invoice lifecycle,
                                      send, cancel, print, and export
                                      invoices.

  Payment Management                  Record payments, validate amounts,
                                      associate payments with invoices,
                                      and calculate outstanding balances.

  Financial Reporting                 Display revenue, payment summaries,
                                      overdue invoices, active
                                      subscriptions, filters, and
                                      exports.

  Reliability and Performance         Prevent duplicate operations,
                                      validate financial data, paginate
                                      large lists, and optimize queries.
  -----------------------------------------------------------------------

### Suggested Module 4 API contract

The exact routes depend on the team's backend framework. Agree on
request and response shapes before parallel implementation.

  -----------------------------------------------------------------------
  Operation                           Purpose
  ----------------------------------- -----------------------------------
  `GET /invoices`                     List invoices with pagination and
                                      filters.

  `GET /invoices/:id`                 Retrieve one invoice and its lines.

  `POST /invoices/generate`           Generate an invoice for an eligible
                                      subscription and billing cycle.

  `POST /invoices/:id/confirm`        Confirm an eligible draft invoice.

  `POST /invoices/:id/cancel`         Cancel an eligible invoice.

  `GET /invoices/:id/pdf`             Generate or retrieve a printable
                                      invoice.

  `GET /invoices/:id/payments`        List payments associated with an
                                      invoice.

  `POST /payments`                    Record a payment against an
                                      invoice.

  `GET /payments`                     List payments with pagination and
                                      filters.

  `GET /reports/summary`              Retrieve financial dashboard
                                      summary data.

  `GET /reports/revenue`              Retrieve revenue report data.

  `GET /reports/outstanding`          Retrieve outstanding and overdue
                                      invoice data.
  -----------------------------------------------------------------------

**API contract requirements:** Document authentication, required fields,
response shapes, validation errors, pagination format, and authorization
for each endpoint. Do not assume these example routes already exist.

------------------------------------------------------------------------

## 7. Conceptual Database Relationships

The following is a conceptual relationship diagram. It is a discussion
baseline, not a finalized database schema. Confirm table names, keys,
optional relationships, and cardinalities with all module owners before
implementing migrations.

``` mermaid
erDiagram
    USERS ||--o{ CUSTOMERS : manages
    CUSTOMERS ||--o{ SUBSCRIPTIONS : owns
    PRODUCTS ||--o{ PRODUCT_VARIANTS : has
    PRODUCTS ||--o{ SUBSCRIPTION_LINES : included_in
    PLANS ||--o{ SUBSCRIPTIONS : defines
    SUBSCRIPTIONS ||--|{ SUBSCRIPTION_LINES : contains
    SUBSCRIPTIONS ||--o{ INVOICES : generates
    INVOICES ||--|{ INVOICE_LINES : contains
    INVOICES ||--o{ PAYMENTS : receives
    TAX_RULES ||--o{ INVOICE_LINES : applies
    DISCOUNTS ||--o{ INVOICES : applies
```

### Important data concepts

-   **Customer:** The customer account that owns subscriptions and
    receives invoices.
-   **Subscription:** The agreement that defines the customer, plan,
    billing schedule, dates, and lifecycle state.
-   **Subscription line:** The products, quantities, and agreed prices
    included in a subscription.
-   **Invoice:** A billing record for a subscription and a specific
    billing cycle.
-   **Invoice line:** The billed product/service, quantity, unit price,
    tax, discount allocation, and line total.
-   **Payment:** A recorded payment with amount, method, date, note, and
    invoice reference.
-   **Tax and discount rules:** Configured rules used when calculating
    eligible invoice amounts.

### Data consistency rules

-   Use stable primary keys and foreign keys.
-   Store monetary amounts using an appropriate fixed-precision decimal
    type, not floating-point arithmetic.
-   Define currency and rounding rules.
-   Store timestamps consistently and apply the business timezone when
    determining billing and due dates.
-   Preserve the invoice calculation details used at the time of
    billing, so later changes to a product or tax rule do not silently
    rewrite historical invoices.
-   Use database transactions for operations that must update multiple
    related records together.
-   Add indexes for frequently filtered fields such as customer ID,
    subscription ID, invoice number, status, due date, and payment date.

------------------------------------------------------------------------

## 8. Module Responsibilities

  -----------------------------------------------------------------------
  Module                  Owner                   Main deliverables
  ----------------------- ----------------------- -----------------------
  Module 1                Member 1                Authentication,
                                                  customer management,
                                                  roles, and access
                                                  control

  Module 2                Member 2                Products, variants,
                                                  plans, tax rules, and
                                                  discounts

  Module 3                Member 3                Quotation templates,
                                                  quotations,
                                                  subscriptions, and
                                                  lifecycle

  Module 4                Member 4                Invoice management,
                                                  payments, financial
                                                  dashboard, and reports
  -----------------------------------------------------------------------

### Module 4 issue breakdown

  Issue   Scope                                         Priority
  ------- --------------------------------------------- -----------
  #1      Automatic invoice generation                  High
  #2      Invoice status and lifecycle                  High
  #3      Invoice viewing, PDF, and printing            Medium
  #4      Payment recording system                      High
  #5      Outstanding balance and overdue tracking      High
  #6      Admin financial dashboard                     Medium
  #7      Revenue and payment reports                   Medium
  #8      Invoice and payment filtering                 Medium
  #9      Billing validation and duplicate prevention   High
  #10     Performance optimization and testing          Important

------------------------------------------------------------------------

## 9. Business Rules and Integration Contracts

Before implementation, all four members should agree on the following:

### Shared contracts

-   Customer, user, product, plan, subscription, invoice, and payment
    identifiers.
-   Database table names and ownership.
-   API request and response formats.
-   Date, time, timezone, currency, and rounding conventions.
-   Role permissions and which module enforces them.
-   Error response format and validation conventions.

### Billing rules

-   What event or scheduled job triggers recurring billing?
-   How is a billing cycle uniquely identified?
-   What happens if invoice generation fails and retries?
-   Which date determines the invoice due date?
-   Can an invoice be partially paid?
-   How are overpayments handled?
-   Which invoice states can be cancelled?
-   How are refunds, reversals, and failed payments represented, if
    supported?
-   Does a discount apply to the next invoice, and how is its usage
    limit reserved or consumed?

Record agreed answers in the project documentation. Do not let different
modules implement conflicting rules.

------------------------------------------------------------------------

## 10. Development and Git Workflow

Use separate feature branches so that each member can work
independently.

``` mermaid
flowchart TD
    A["Create GitHub Issue"] --> B["Assign Issue to Owner"]
    B --> C["Create Feature Branch"]
    C --> D["Implement Functionality"]
    D --> E["Run Tests"]
    E --> F{"Tests Pass?"}
    F -->|No| D
    F -->|Yes| G["Create Pull Request"]
    G --> H["Link Pull Request to Issue"]
    H --> I["Code Review"]
    I --> J{"Approved?"}
    J -->|No| D
    J -->|Yes| K["Merge into Integration Branch"]
    K --> L["Run Integration Tests"]
    L --> M["Merge Stable Work into Main"]
```

### Suggested branch names

``` text
main
integration

feature/auth-customer
feature/products-plans
feature/quotations-subscriptions
feature/invoices-payments
feature/financial-reports
```

### Team rules

1.  Do not commit unfinished work directly to `main`.
2.  Create a GitHub Issue for each independently trackable task or bug.
3.  Work on a feature branch.
4.  Commit changes with clear messages.
5.  Include database migrations and relevant tests in the Pull Request.
6.  Link each Pull Request to its GitHub Issue.
7.  Request review before merging.
8.  Test the integrated workflow, not only individual modules.
9.  Do not overwrite another member's migrations or shared API contracts
    without discussion.
10. Keep the README updated when an agreed workflow or contract changes.

### Required Pull Request submission

Each member should provide:

-   Source code for the assigned functionality.
-   Database migrations or schema changes.
-   API endpoints and documentation.
-   Screenshots or a short demonstration.
-   Test cases and results.
-   Known bugs and unresolved issues.
-   A Pull Request linked to the relevant issue.

------------------------------------------------------------------------

## 11. Testing Checklist

### Invoice tests

-   [ ] Invoice generated for an eligible subscription.
-   [ ] No invoice generated before the billing date.
-   [ ] Duplicate generation attempt is safely rejected or ignored.
-   [ ] Customer and subscription details are correct.
-   [ ] Product lines and quantities are correct.
-   [ ] Tax and discount calculations are correct.
-   [ ] Invoice total and rounding are correct.
-   [ ] Invalid status transitions are rejected.
-   [ ] PDF and print output are accurate.

### Payment tests

-   [ ] Valid payment is recorded.
-   [ ] Payment is linked to the correct invoice.
-   [ ] Partial payment updates the outstanding balance.
-   [ ] Full payment changes the invoice to Paid.
-   [ ] Zero and negative payment amounts are rejected.
-   [ ] Payment above the outstanding balance follows the agreed
    overpayment rule.
-   [ ] Retried payment requests do not create duplicates.
-   [ ] Payment history is accurate.

### Reporting tests

-   [ ] Revenue includes only amounts counted as received under the
    agreed accounting rule.
-   [ ] Outstanding balances match invoice and payment records.
-   [ ] Overdue invoices use the correct due-date logic.
-   [ ] Active subscription counts match subscription records.
-   [ ] Date and status filters return correct results.
-   [ ] Exported reports match displayed data.
-   [ ] Large lists use pagination or another agreed strategy.
-   [ ] Key pages meet the under-two-second response target in the
    agreed test environment.

### Security tests

-   [ ] Customers can only view their own invoices and subscriptions.
-   [ ] Staff cannot perform admin-only actions.
-   [ ] Unauthorized API requests are rejected.
-   [ ] Payment and invoice operations validate ownership and
    permissions on the backend.

------------------------------------------------------------------------

## 12. Setup Instructions

> Replace the placeholders below with the actual repository setup
> details once the team finalizes the technology stack.

### Prerequisites

-   [ ] Required runtime and version: `TODO`
-   [ ] Package manager: `TODO`
-   [ ] Database and version: `TODO`
-   [ ] Environment variables: see `.env.example`

### Installation

``` bash
# Clone the repository
git clone <REPOSITORY_URL>

# Enter the project directory
cd <PROJECT_DIRECTORY>

# Install dependencies
<INSTALL_COMMAND>

# Configure environment variables
# Copy .env.example to .env and fill in local values

# Run database migrations
<MIGRATION_COMMAND>

# Start the development server
<START_COMMAND>
```

### Environment variables

Document variable names in `.env.example`, but never commit real
secrets.

``` env
DATABASE_URL=
AUTH_SECRET=
APP_URL=
```

### Running tests

``` bash
<TEST_COMMAND>
```

------------------------------------------------------------------------

## Project Reference

Use this README as the shared reference for system flow and module
integration. If an implementation decision differs from a diagram,
discuss and document the change so that all four modules continue to
follow the same contracts.

**Primary integration path:**

`Users and Customers → Products and Plans → Quotations and Subscriptions → Invoices and Payments → Financial Reports`
