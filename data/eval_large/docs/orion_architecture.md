# Orion Retail Platform Architecture

## 1. About this document

This document describes every service that runs the Orion Retail website and apps. Each service has its own section that explains what it does, which team owns it, which other services it needs, and how it is operated. There is deliberately no single dependency diagram: dependencies change every week, so each service section is the source of truth for that service only.

Teams are listed at the end of the document with their leads and planning days. When a service changes owner, the service section is updated first and the team list second.

## 2. How services are operated

Every service is deployed to at least two regions so that one region can fail without taking the shop down. Each service has a p99 latency target and an availability target that the owning team reviews every quarter. When a target is missed two quarters in a row, the team must present a recovery plan at the architecture review.

A service may only depend on services in a lower layer of the platform. Calls in the other direction must go through the Event Bus as events, which keeps the platform free of circular dependencies.

## 3. Services

## Platform services

### Event Bus

The Event Bus carries events between services so they never call each other synchronously for updates. The Event Bus is owned by the Platform team. The Event Bus does not depend on any other service.

It runs 8 replicas in the Mumbai region and is deployed twice a week. The Event Bus has a p99 latency target of 150 ms. Its availability target is 99.9 percent. Capacity is reviewed every quarter against the traffic forecast. It exposes a health endpoint that the load balancer checks every ten seconds. A runbook describes how to drain traffic from one region during an incident. The service writes structured logs that are kept for thirty days. The team keeps a list of known failure modes and how each one was last fixed. Error messages from it never include customer personal data.

### Cache Cluster

The Cache Cluster keeps frequently read data in memory so that hot pages load without touching the databases. The Cache Cluster is owned by the Platform team. The Cache Cluster does not depend on any other service.

It runs 2 replicas in the Frankfurt region and is deployed daily. The Cache Cluster has a p99 latency target of 400 ms. Its availability target is 99.99 percent. It exposes a health endpoint that the load balancer checks every ten seconds. It was last reviewed for security in the most recent annual audit. A runbook describes how to drain traffic from one region during an incident. The service writes structured logs that are kept for thirty days. Feature flags let the team switch new behaviour off without a deployment. Load tests run against it before every major sales event.

### Config Service

The Config Service stores feature flags and runtime settings that every service reads at start-up. The Config Service is owned by the Platform team. The Config Service does not depend on any other service.

It runs 8 replicas in the Virginia region and is deployed twice a week. The Config Service has a p99 latency target of 400 ms. Its availability target is 99.9 percent. All of its configuration is stored in version control and reviewed before release. Feature flags let the team switch new behaviour off without a deployment. Capacity is reviewed every quarter against the traffic forecast. The team keeps a list of known failure modes and how each one was last fixed. Load tests run against it before every major sales event. Synthetic checks call it from outside the data centre every minute.

### Service Mesh

The Service Mesh encrypts traffic between services and retries calls that fail because of network blips. The Service Mesh is owned by the Platform team. The Service Mesh depends on the Search Index.

It runs 2 replicas in the Frankfurt region and is deployed weekly. The Service Mesh has a p99 latency target of 150 ms. Its availability target is 99.9 percent. It exposes a health endpoint that the load balancer checks every ten seconds. All of its configuration is stored in version control and reviewed before release. Its dashboards show request rate, error rate, and saturation side by side. Load tests run against it before every major sales event. The team keeps a list of known failure modes and how each one was last fixed. Database migrations for it must be backwards compatible for one release.

### Job Scheduler

The Job Scheduler runs timed background jobs such as nightly clean-ups and hourly exports. The Job Scheduler is owned by the Platform team. The Job Scheduler depends on the Event Bus, the Metrics Pipeline, and the Secrets Vault.

It runs 4 replicas in the Frankfurt region and is deployed daily. The Job Scheduler has a p99 latency target of 50 ms. Its availability target is 99.95 percent. The service writes structured logs that are kept for thirty days. Load tests run against it before every major sales event. Changes go through a canary release that receives five percent of traffic for thirty minutes. Error messages from it never include customer personal data. All of its configuration is stored in version control and reviewed before release. Synthetic checks call it from outside the data centre every minute.

### API Gateway

The API Gateway receives every request from the mobile apps and the website and forwards it to the right service. The API Gateway is owned by the Platform team. The API Gateway depends on the Shipment Tracker.

It runs 6 replicas in the Mumbai region and is deployed weekly. The API Gateway has a p99 latency target of 300 ms. Its availability target is 99.99 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. All of its configuration is stored in version control and reviewed before release. Its on-call rotation hands over every Monday at ten in the morning. A runbook describes how to drain traffic from one region during an incident. Feature flags let the team switch new behaviour off without a deployment. Changes go through a canary release that receives five percent of traffic for thirty minutes.

## Data Platform services

### Postgres Cluster

The Postgres Cluster is the main relational database that holds orders, accounts, and stock levels. The Postgres Cluster is owned by the Data Platform team. The Postgres Cluster does not depend on any other service.

It runs 3 replicas in the Virginia region and is deployed weekly. The Postgres Cluster has a p99 latency target of 400 ms. Its availability target is 99.95 percent. A runbook describes how to drain traffic from one region during an incident. Capacity is reviewed every quarter against the traffic forecast. Synthetic checks call it from outside the data centre every minute. Its on-call rotation hands over every Monday at ten in the morning. It was last reviewed for security in the most recent annual audit. Changes go through a canary release that receives five percent of traffic for thirty minutes.

### Object Store

The Object Store keeps large files such as product photos, invoices, and exported reports. The Object Store is owned by the Data Platform team. The Object Store does not depend on any other service.

It runs 6 replicas in the Singapore region and is deployed weekly. The Object Store has a p99 latency target of 20 ms. Its availability target is 99.99 percent. The service writes structured logs that are kept for thirty days. The team keeps a list of known failure modes and how each one was last fixed. It was last reviewed for security in the most recent annual audit. Feature flags let the team switch new behaviour off without a deployment. Synthetic checks call it from outside the data centre every minute. Its alerts page the owning team only during working hours unless an error budget is burning fast.

### Search Index

The Search Index holds a full-text index of products so that searches return results in milliseconds. The Search Index is owned by the Data Platform team. The Search Index does not depend on any other service.

It runs 3 replicas in the Singapore region and is deployed several times a day. The Search Index has a p99 latency target of 250 ms. Its availability target is 99.99 percent. It was last reviewed for security in the most recent annual audit. Its on-call rotation hands over every Monday at ten in the morning. A runbook describes how to drain traffic from one region during an incident. The service writes structured logs that are kept for thirty days. It exposes a health endpoint that the load balancer checks every ten seconds. The team keeps a list of known failure modes and how each one was last fixed.

### Metrics Pipeline

The Metrics Pipeline collects counters and timings from every service and sends them to the dashboards. The Metrics Pipeline is owned by the Data Platform team. The Metrics Pipeline does not depend on any other service.

It runs 2 replicas in the Singapore region and is deployed several times a day. The Metrics Pipeline has a p99 latency target of 300 ms. Its availability target is 99.99 percent. Load tests run against it before every major sales event. It exposes a health endpoint that the load balancer checks every ten seconds. The team keeps a list of known failure modes and how each one was last fixed. The service writes structured logs that are kept for thirty days. Capacity is reviewed every quarter against the traffic forecast. It was last reviewed for security in the most recent annual audit.

### Stream Processor

The Stream Processor reads the event stream and computes running totals such as sales per minute. The Stream Processor is owned by the Data Platform team. The Stream Processor depends on the Event Bus, the Object Store, and the Search Index.

It runs 4 replicas in the Frankfurt region and is deployed weekly. The Stream Processor has a p99 latency target of 200 ms. Its availability target is 99.9 percent. Database migrations for it must be backwards compatible for one release. It exposes a health endpoint that the load balancer checks every ten seconds. Load tests run against it before every major sales event. Synthetic checks call it from outside the data centre every minute. It was last reviewed for security in the most recent annual audit. A runbook describes how to drain traffic from one region during an incident.

### Data Warehouse

The Data Warehouse stores the full history of business data for analysts to query. The Data Warehouse is owned by the Data Platform team. The Data Warehouse depends on the User Accounts.

It runs 3 replicas in the Virginia region and is deployed daily. The Data Warehouse has a p99 latency target of 200 ms. Its availability target is 99.9 percent. The team keeps a list of known failure modes and how each one was last fixed. Error messages from it never include customer personal data. All of its configuration is stored in version control and reviewed before release. Its on-call rotation hands over every Monday at ten in the morning. Database migrations for it must be backwards compatible for one release. It exposes a health endpoint that the load balancer checks every ten seconds.

## Security services

### Secrets Vault

The Secrets Vault stores passwords, API keys, and certificates and hands them only to approved services. The Secrets Vault is owned by the Security team. The Secrets Vault does not depend on any other service.

It runs 8 replicas in the Mumbai region and is deployed daily. The Secrets Vault has a p99 latency target of 200 ms. Its availability target is 99.9 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Feature flags let the team switch new behaviour off without a deployment. All of its configuration is stored in version control and reviewed before release. Synthetic checks call it from outside the data centre every minute. The service writes structured logs that are kept for thirty days. Database migrations for it must be backwards compatible for one release.

### Token Service

The Token Service issues and verifies the signed tokens that prove a request comes from a logged-in user. The Token Service is owned by the Security team. The Token Service depends on the Cache Cluster and the Object Store.

It runs 3 replicas in the Frankfurt region and is deployed weekly. The Token Service has a p99 latency target of 200 ms. Its availability target is 99.9 percent. It was last reviewed for security in the most recent annual audit. Database migrations for it must be backwards compatible for one release. The team keeps a list of known failure modes and how each one was last fixed. Changes go through a canary release that receives five percent of traffic for thirty minutes. It exposes a health endpoint that the load balancer checks every ten seconds. Its alerts page the owning team only during working hours unless an error budget is burning fast.

### Key Rotation Service

The Key Rotation Service replaces every encryption key every 90 days so a leaked key stops working quickly. The Key Rotation Service is owned by the Security team. The Key Rotation Service depends on the Cache Cluster.

It runs 2 replicas in the Virginia region and is deployed several times a day. The Key Rotation Service has a p99 latency target of 35 ms. Its availability target is 99.99 percent. Changes go through a canary release that receives five percent of traffic for thirty minutes. Load tests run against it before every major sales event. Error messages from it never include customer personal data. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. It was last reviewed for security in the most recent annual audit.

### Audit Log

The Audit Log records who changed what and when, and keeps the records for seven years. The Audit Log is owned by the Security team. The Audit Log depends on the Event Bus, the Cache Cluster, and the Object Store.

It runs 2 replicas in the Frankfurt region and is deployed weekly. The Audit Log has a p99 latency target of 250 ms. Its availability target is 99.95 percent. Its on-call rotation hands over every Monday at ten in the morning. Database migrations for it must be backwards compatible for one release. It exposes a health endpoint that the load balancer checks every ten seconds. Error messages from it never include customer personal data. Feature flags let the team switch new behaviour off without a deployment. Load tests run against it before every major sales event.

### Fraud Engine

The Fraud Engine scores each payment for the risk that it was made with stolen card details. The Fraud Engine is owned by the Security team. The Fraud Engine depends on the Token Service.

It runs 8 replicas in the Singapore region and is deployed weekly. The Fraud Engine has a p99 latency target of 200 ms. Its availability target is 99.99 percent. It was last reviewed for security in the most recent annual audit. It exposes a health endpoint that the load balancer checks every ten seconds. Load tests run against it before every major sales event. The team keeps a list of known failure modes and how each one was last fixed. Error messages from it never include customer personal data. Its dashboards show request rate, error rate, and saturation side by side.

### Consent Manager

The Consent Manager remembers which kinds of marketing each customer agreed to receive. The Consent Manager is owned by the Security team. The Consent Manager depends on the Job Scheduler, the Audit Log, and the Address Validator.

It runs 3 replicas in the Singapore region and is deployed weekly. The Consent Manager has a p99 latency target of 20 ms. Its availability target is 99.95 percent. Load tests run against it before every major sales event. Capacity is reviewed every quarter against the traffic forecast. All of its configuration is stored in version control and reviewed before release. A runbook describes how to drain traffic from one region during an incident. Changes go through a canary release that receives five percent of traffic for thirty minutes. Its on-call rotation hands over every Monday at ten in the morning.

## Identity services

### User Accounts

The User Accounts stores customer accounts, email addresses, and password hashes. The User Accounts is owned by the Identity team. The User Accounts depends on the Event Bus.

It runs 2 replicas in the Frankfurt region and is deployed daily. The User Accounts has a p99 latency target of 80 ms. Its availability target is 99.9 percent. Database migrations for it must be backwards compatible for one release. Synthetic checks call it from outside the data centre every minute. Changes go through a canary release that receives five percent of traffic for thirty minutes. Error messages from it never include customer personal data. The service writes structured logs that are kept for thirty days. Its on-call rotation hands over every Monday at ten in the morning.

### Session Store

The Session Store remembers who is logged in on which device until the session expires. The Session Store is owned by the Identity team. The Session Store depends on the Event Bus, the Config Service, and the Secrets Vault.

It runs 4 replicas in the Singapore region and is deployed daily. The Session Store has a p99 latency target of 35 ms. Its availability target is 99.9 percent. Error messages from it never include customer personal data. Load tests run against it before every major sales event. The team keeps a list of known failure modes and how each one was last fixed. Changes go through a canary release that receives five percent of traffic for thirty minutes. Capacity is reviewed every quarter against the traffic forecast. All of its configuration is stored in version control and reviewed before release.

### Login Service

The Login Service checks passwords and starts a session when a customer signs in. The Login Service is owned by the Identity team. The Login Service depends on the Object Store and the Inventory Ledger.

It runs 3 replicas in the Frankfurt region and is deployed twice a week. The Login Service has a p99 latency target of 80 ms. Its availability target is 99.99 percent. Feature flags let the team switch new behaviour off without a deployment. It exposes a health endpoint that the load balancer checks every ten seconds. Capacity is reviewed every quarter against the traffic forecast. A runbook describes how to drain traffic from one region during an incident. It was last reviewed for security in the most recent annual audit. Load tests run against it before every major sales event.

### Profile Service

The Profile Service stores names, saved addresses, and preferences that customers edit in their account page. The Profile Service is owned by the Identity team. The Profile Service depends on the Job Scheduler, the Token Service, and the Image Service.

It runs 2 replicas in the Mumbai region and is deployed weekly. The Profile Service has a p99 latency target of 250 ms. Its availability target is 99.99 percent. The team keeps a list of known failure modes and how each one was last fixed. Its alerts page the owning team only during working hours unless an error budget is burning fast. A runbook describes how to drain traffic from one region during an incident. It exposes a health endpoint that the load balancer checks every ten seconds. All of its configuration is stored in version control and reviewed before release. It was last reviewed for security in the most recent annual audit.

### Permissions Service

The Permissions Service decides which staff members may open which internal tools. The Permissions Service is owned by the Identity team. The Permissions Service depends on the Audit Log.

It runs 4 replicas in the Mumbai region and is deployed twice a week. The Permissions Service has a p99 latency target of 50 ms. Its availability target is 99.99 percent. Database migrations for it must be backwards compatible for one release. It exposes a health endpoint that the load balancer checks every ten seconds. Changes go through a canary release that receives five percent of traffic for thirty minutes. Feature flags let the team switch new behaviour off without a deployment. Load tests run against it before every major sales event. Synthetic checks call it from outside the data centre every minute.

### Two Factor Service

The Two Factor Service sends one-time codes and checks them when a login looks unusual. The Two Factor Service is owned by the Identity team. The Two Factor Service depends on the Postgres Cluster and the User Accounts.

It runs 4 replicas in the Frankfurt region and is deployed weekly. The Two Factor Service has a p99 latency target of 35 ms. Its availability target is 99.9 percent. A runbook describes how to drain traffic from one region during an incident. Its dashboards show request rate, error rate, and saturation side by side. Synthetic checks call it from outside the data centre every minute. The service writes structured logs that are kept for thirty days. Capacity is reviewed every quarter against the traffic forecast. Its on-call rotation hands over every Monday at ten in the morning.

## Catalog services

### Product Catalog

The Product Catalog holds product titles, descriptions, sizes, and colours for everything Orion sells. The Product Catalog is owned by the Catalog team. The Product Catalog depends on the Event Bus, the Cache Cluster, and the Search Index.

It runs 3 replicas in the Singapore region and is deployed weekly. The Product Catalog has a p99 latency target of 150 ms. Its availability target is 99.99 percent. It was last reviewed for security in the most recent annual audit. The team keeps a list of known failure modes and how each one was last fixed. A runbook describes how to drain traffic from one region during an incident. Changes go through a canary release that receives five percent of traffic for thirty minutes. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast.

### Inventory Ledger

The Inventory Ledger records every change to stock so that the count of items on hand is always exact. The Inventory Ledger is owned by the Catalog team. The Inventory Ledger depends on the Postgres Cluster and the Metrics Pipeline.

It runs 2 replicas in the Singapore region and is deployed several times a day. The Inventory Ledger has a p99 latency target of 400 ms. Its availability target is 99.95 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Its on-call rotation hands over every Monday at ten in the morning. Changes go through a canary release that receives five percent of traffic for thirty minutes. Synthetic checks call it from outside the data centre every minute. Its dashboards show request rate, error rate, and saturation side by side. Feature flags let the team switch new behaviour off without a deployment.

### Image Service

The Image Service resizes and crops product photos for phones, tablets, and desktops. The Image Service is owned by the Catalog team. The Image Service depends on the Postgres Cluster and the Metrics Pipeline.

It runs 4 replicas in the Singapore region and is deployed several times a day. The Image Service has a p99 latency target of 20 ms. Its availability target is 99.9 percent. Error messages from it never include customer personal data. Its alerts page the owning team only during working hours unless an error budget is burning fast. A runbook describes how to drain traffic from one region during an incident. It exposes a health endpoint that the load balancer checks every ten seconds. Capacity is reviewed every quarter against the traffic forecast. Its dashboards show request rate, error rate, and saturation side by side.

### Pricing Engine

The Pricing Engine calculates the current price of each product, including regional prices. The Pricing Engine is owned by the Catalog team. The Pricing Engine depends on the Job Scheduler and the SMS Gateway.

It runs 8 replicas in the Singapore region and is deployed twice a week. The Pricing Engine has a p99 latency target of 35 ms. Its availability target is 99.99 percent. All of its configuration is stored in version control and reviewed before release. Changes go through a canary release that receives five percent of traffic for thirty minutes. The service writes structured logs that are kept for thirty days. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. Feature flags let the team switch new behaviour off without a deployment.

### Recommendation Engine

The Recommendation Engine suggests products a customer is likely to want based on what similar shoppers bought. The Recommendation Engine is owned by the Catalog team. The Recommendation Engine depends on the Pricing Engine.

It runs 4 replicas in the Frankfurt region and is deployed twice a week. The Recommendation Engine has a p99 latency target of 20 ms. Its availability target is 99.99 percent. Capacity is reviewed every quarter against the traffic forecast. Its dashboards show request rate, error rate, and saturation side by side. All of its configuration is stored in version control and reviewed before release. It exposes a health endpoint that the load balancer checks every ten seconds. Its on-call rotation hands over every Monday at ten in the morning. The service writes structured logs that are kept for thirty days.

### Search Frontend

The Search Frontend turns what a shopper types into a product search and ranks the results. The Search Frontend is owned by the Catalog team. The Search Frontend depends on the Pricing Engine.

It runs 2 replicas in the Singapore region and is deployed weekly. The Search Frontend has a p99 latency target of 400 ms. Its availability target is 99.95 percent. Changes go through a canary release that receives five percent of traffic for thirty minutes. Its alerts page the owning team only during working hours unless an error budget is burning fast. Error messages from it never include customer personal data. The team keeps a list of known failure modes and how each one was last fixed. It exposes a health endpoint that the load balancer checks every ten seconds. Synthetic checks call it from outside the data centre every minute.

## Checkout services

### Address Validator

The Address Validator checks that a shipping address really exists and corrects common spelling mistakes in street names. The Address Validator is owned by the Checkout team. The Address Validator depends on the Config Service, the Postgres Cluster, and the Object Store.

It runs 3 replicas in the Virginia region and is deployed weekly. The Address Validator has a p99 latency target of 50 ms. Its availability target is 99.95 percent. Load tests run against it before every major sales event. Its on-call rotation hands over every Monday at ten in the morning. Feature flags let the team switch new behaviour off without a deployment. Error messages from it never include customer personal data. Capacity is reviewed every quarter against the traffic forecast. Synthetic checks call it from outside the data centre every minute.

### Cart Service

The Cart Service keeps the items a shopper has added to the basket, even across devices. The Cart Service is owned by the Checkout team. The Cart Service depends on the Address Validator and the SMS Gateway.

It runs 8 replicas in the Singapore region and is deployed weekly. The Cart Service has a p99 latency target of 300 ms. Its availability target is 99.95 percent. Capacity is reviewed every quarter against the traffic forecast. Load tests run against it before every major sales event. A runbook describes how to drain traffic from one region during an incident. Error messages from it never include customer personal data. The team keeps a list of known failure modes and how each one was last fixed. Its on-call rotation hands over every Monday at ten in the morning.

### Promotions Service

The Promotions Service applies discount codes and seasonal offers to a basket. The Promotions Service is owned by the Checkout team. The Promotions Service depends on the Stream Processor.

It runs 4 replicas in the Virginia region and is deployed daily. The Promotions Service has a p99 latency target of 35 ms. Its availability target is 99.9 percent. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. Changes go through a canary release that receives five percent of traffic for thirty minutes. Its on-call rotation hands over every Monday at ten in the morning. The team keeps a list of known failure modes and how each one was last fixed. It was last reviewed for security in the most recent annual audit.

### Tax Calculator

The Tax Calculator works out sales tax and VAT for each item based on where it ships. The Tax Calculator is owned by the Checkout team. The Tax Calculator depends on the Email Sender.

It runs 2 replicas in the Singapore region and is deployed twice a week. The Tax Calculator has a p99 latency target of 150 ms. Its availability target is 99.9 percent. Synthetic checks call it from outside the data centre every minute. Feature flags let the team switch new behaviour off without a deployment. It exposes a health endpoint that the load balancer checks every ten seconds. Its on-call rotation hands over every Monday at ten in the morning. Its dashboards show request rate, error rate, and saturation side by side. Database migrations for it must be backwards compatible for one release.

### Checkout Orchestrator

The Checkout Orchestrator guides a basket through address, payment, and confirmation steps in order. The Checkout Orchestrator is owned by the Checkout team. The Checkout Orchestrator depends on the Tax Calculator.

It runs 2 replicas in the Frankfurt region and is deployed twice a week. The Checkout Orchestrator has a p99 latency target of 400 ms. Its availability target is 99.95 percent. A runbook describes how to drain traffic from one region during an incident. The service writes structured logs that are kept for thirty days. Its dashboards show request rate, error rate, and saturation side by side. All of its configuration is stored in version control and reviewed before release. Its alerts page the owning team only during working hours unless an error budget is burning fast. Feature flags let the team switch new behaviour off without a deployment.

### Order Service

The Order Service creates the order record once payment succeeds and tracks its status. The Order Service is owned by the Checkout team. The Order Service depends on the Config Service and the Stock Allocator.

It runs 8 replicas in the Mumbai region and is deployed twice a week. The Order Service has a p99 latency target of 20 ms. Its availability target is 99.95 percent. All of its configuration is stored in version control and reviewed before release. Its alerts page the owning team only during working hours unless an error budget is burning fast. Its dashboards show request rate, error rate, and saturation side by side. Load tests run against it before every major sales event. A runbook describes how to drain traffic from one region during an incident. The service writes structured logs that are kept for thirty days.

## Payments services

### Currency Converter

The Currency Converter shows prices in the shopper's local money using exchange rates refreshed every 15 minutes. The Currency Converter is owned by the Payments team. The Currency Converter depends on the Cache Cluster, the Postgres Cluster, and the Search Index.

It runs 6 replicas in the Mumbai region and is deployed several times a day. The Currency Converter has a p99 latency target of 35 ms. Its availability target is 99.9 percent. It was last reviewed for security in the most recent annual audit. Its dashboards show request rate, error rate, and saturation side by side. It exposes a health endpoint that the load balancer checks every ten seconds. Its on-call rotation hands over every Monday at ten in the morning. Load tests run against it before every major sales event. The team keeps a list of known failure modes and how each one was last fixed.

### Card Processor

The Card Processor sends card payments to the card networks and reads back the approval or decline. The Card Processor is owned by the Payments team. The Card Processor depends on the Token Service, the Image Service, and the Currency Converter.

It runs 4 replicas in the Frankfurt region and is deployed twice a week. The Card Processor has a p99 latency target of 80 ms. Its availability target is 99.9 percent. Its dashboards show request rate, error rate, and saturation side by side. Capacity is reviewed every quarter against the traffic forecast. Database migrations for it must be backwards compatible for one release. Its alerts page the owning team only during working hours unless an error budget is burning fast. Error messages from it never include customer personal data. Synthetic checks call it from outside the data centre every minute.

### Wallet Service

The Wallet Service holds store credit and gift card balances for each customer. The Wallet Service is owned by the Payments team. The Wallet Service depends on the Config Service, the User Accounts, and the Clickstream Collector.

It runs 3 replicas in the Frankfurt region and is deployed weekly. The Wallet Service has a p99 latency target of 400 ms. Its availability target is 99.9 percent. Its dashboards show request rate, error rate, and saturation side by side. Its on-call rotation hands over every Monday at ten in the morning. The team keeps a list of known failure modes and how each one was last fixed. Synthetic checks call it from outside the data centre every minute. Database migrations for it must be backwards compatible for one release. Capacity is reviewed every quarter against the traffic forecast.

### Settlement Service

The Settlement Service moves collected money to Orion's bank account in daily batches. The Settlement Service is owned by the Payments team. The Settlement Service depends on the Stream Processor and the Product Catalog.

It runs 3 replicas in the Virginia region and is deployed daily. The Settlement Service has a p99 latency target of 200 ms. Its availability target is 99.95 percent. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. Feature flags let the team switch new behaviour off without a deployment. The team keeps a list of known failure modes and how each one was last fixed. It exposes a health endpoint that the load balancer checks every ten seconds. Its on-call rotation hands over every Monday at ten in the morning.

### Payment Router

The Payment Router chooses which payment provider handles each payment to keep fees low. The Payment Router is owned by the Payments team. The Payment Router depends on the Consent Manager.

It runs 8 replicas in the Singapore region and is deployed several times a day. The Payment Router has a p99 latency target of 50 ms. Its availability target is 99.99 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Feature flags let the team switch new behaviour off without a deployment. Its on-call rotation hands over every Monday at ten in the morning. Database migrations for it must be backwards compatible for one release. The team keeps a list of known failure modes and how each one was last fixed. Error messages from it never include customer personal data.

### Refund Service

The Refund Service returns money to the original payment method when an order is cancelled or returned. The Refund Service is owned by the Payments team. The Refund Service depends on the Profile Service, the Promotions Service, and the Settlement Service.

It runs 2 replicas in the Mumbai region and is deployed several times a day. The Refund Service has a p99 latency target of 120 ms. Its availability target is 99.9 percent. Its dashboards show request rate, error rate, and saturation side by side. Its on-call rotation hands over every Monday at ten in the morning. A runbook describes how to drain traffic from one region during an incident. Changes go through a canary release that receives five percent of traffic for thirty minutes. Capacity is reviewed every quarter against the traffic forecast. All of its configuration is stored in version control and reviewed before release.

## Fulfilment services

### Warehouse Manager

The Warehouse Manager tracks which shelf in which warehouse holds each item. The Warehouse Manager is owned by the Fulfilment team. The Warehouse Manager depends on the Key Rotation Service, the Inventory Ledger, and the SMS Gateway.

It runs 8 replicas in the Mumbai region and is deployed several times a day. The Warehouse Manager has a p99 latency target of 150 ms. Its availability target is 99.99 percent. All of its configuration is stored in version control and reviewed before release. It was last reviewed for security in the most recent annual audit. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. Error messages from it never include customer personal data. Changes go through a canary release that receives five percent of traffic for thirty minutes.

### Stock Allocator

The Stock Allocator decides which warehouse should ship each order line. The Stock Allocator is owned by the Fulfilment team. The Stock Allocator depends on the Address Validator.

It runs 6 replicas in the Singapore region and is deployed weekly. The Stock Allocator has a p99 latency target of 400 ms. Its availability target is 99.95 percent. The service writes structured logs that are kept for thirty days. Feature flags let the team switch new behaviour off without a deployment. Its dashboards show request rate, error rate, and saturation side by side. Load tests run against it before every major sales event. The team keeps a list of known failure modes and how each one was last fixed. Synthetic checks call it from outside the data centre every minute.

### Picking Planner

The Picking Planner plans the route warehouse staff walk to collect items so the walking distance stays short. The Picking Planner is owned by the Fulfilment team. The Picking Planner depends on the Stream Processor and the Warehouse Manager.

It runs 6 replicas in the Singapore region and is deployed several times a day. The Picking Planner has a p99 latency target of 150 ms. Its availability target is 99.95 percent. The service writes structured logs that are kept for thirty days. All of its configuration is stored in version control and reviewed before release. Its on-call rotation hands over every Monday at ten in the morning. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast. Database migrations for it must be backwards compatible for one release.

### Packing Service

The Packing Service chooses the box size and prints the packing slip for each parcel. The Packing Service is owned by the Fulfilment team. The Packing Service depends on the Postgres Cluster and the Login Service.

It runs 8 replicas in the Singapore region and is deployed several times a day. The Packing Service has a p99 latency target of 250 ms. Its availability target is 99.9 percent. Its on-call rotation hands over every Monday at ten in the morning. Its dashboards show request rate, error rate, and saturation side by side. It was last reviewed for security in the most recent annual audit. The team keeps a list of known failure modes and how each one was last fixed. Synthetic checks call it from outside the data centre every minute. Error messages from it never include customer personal data.

### Shipment Tracker

The Shipment Tracker follows each parcel with the courier and updates its delivery status. The Shipment Tracker is owned by the Fulfilment team. The Shipment Tracker depends on the Service Mesh and the Two Factor Service.

It runs 6 replicas in the Virginia region and is deployed twice a week. The Shipment Tracker has a p99 latency target of 35 ms. Its availability target is 99.9 percent. It was last reviewed for security in the most recent annual audit. Its dashboards show request rate, error rate, and saturation side by side. Its on-call rotation hands over every Monday at ten in the morning. Changes go through a canary release that receives five percent of traffic for thirty minutes. The team keeps a list of known failure modes and how each one was last fixed. Load tests run against it before every major sales event.

### Returns Service

The Returns Service books return pickups and checks returned items back into stock. The Returns Service is owned by the Fulfilment team. The Returns Service depends on the Experiment Platform.

It runs 8 replicas in the Singapore region and is deployed twice a week. The Returns Service has a p99 latency target of 35 ms. Its availability target is 99.95 percent. Error messages from it never include customer personal data. All of its configuration is stored in version control and reviewed before release. It was last reviewed for security in the most recent annual audit. Synthetic checks call it from outside the data centre every minute. Changes go through a canary release that receives five percent of traffic for thirty minutes. It exposes a health endpoint that the load balancer checks every ten seconds.

## Customer services

### Email Sender

The Email Sender delivers transactional emails such as receipts and password resets. The Email Sender is owned by the Customer team. The Email Sender depends on the Metrics Pipeline and the Secrets Vault.

It runs 2 replicas in the Frankfurt region and is deployed weekly. The Email Sender has a p99 latency target of 250 ms. Its availability target is 99.95 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Its dashboards show request rate, error rate, and saturation side by side. All of its configuration is stored in version control and reviewed before release. Changes go through a canary release that receives five percent of traffic for thirty minutes. It exposes a health endpoint that the load balancer checks every ten seconds. Feature flags let the team switch new behaviour off without a deployment.

### SMS Gateway

The SMS Gateway delivers text messages through local mobile carriers. The SMS Gateway is owned by the Customer team. The SMS Gateway depends on the Secrets Vault.

It runs 3 replicas in the Frankfurt region and is deployed twice a week. The SMS Gateway has a p99 latency target of 250 ms. Its availability target is 99.9 percent. The service writes structured logs that are kept for thirty days. Database migrations for it must be backwards compatible for one release. Changes go through a canary release that receives five percent of traffic for thirty minutes. It was last reviewed for security in the most recent annual audit. The team keeps a list of known failure modes and how each one was last fixed. It exposes a health endpoint that the load balancer checks every ten seconds.

### Notification Hub

The Notification Hub decides whether to tell a customer something by email, text, or app notification. The Notification Hub is owned by the Customer team. The Notification Hub depends on the Key Rotation Service and the Audit Log.

It runs 3 replicas in the Virginia region and is deployed weekly. The Notification Hub has a p99 latency target of 250 ms. Its availability target is 99.99 percent. It exposes a health endpoint that the load balancer checks every ten seconds. Error messages from it never include customer personal data. Changes go through a canary release that receives five percent of traffic for thirty minutes. The team keeps a list of known failure modes and how each one was last fixed. A runbook describes how to drain traffic from one region during an incident. Load tests run against it before every major sales event.

### Reviews Service

The Reviews Service collects product ratings and hides reviews that break the posting rules. The Reviews Service is owned by the Customer team. The Reviews Service depends on the Cart Service.

It runs 6 replicas in the Frankfurt region and is deployed daily. The Reviews Service has a p99 latency target of 250 ms. Its availability target is 99.9 percent. A runbook describes how to drain traffic from one region during an incident. Its alerts page the owning team only during working hours unless an error budget is burning fast. All of its configuration is stored in version control and reviewed before release. Its on-call rotation hands over every Monday at ten in the morning. Feature flags let the team switch new behaviour off without a deployment. Capacity is reviewed every quarter against the traffic forecast.

### Loyalty Service

The Loyalty Service awards points for purchases and lets members spend them on later orders. The Loyalty Service is owned by the Customer team. The Loyalty Service depends on the Consent Manager, the Inventory Ledger, and the Settlement Service.

It runs 6 replicas in the Frankfurt region and is deployed weekly. The Loyalty Service has a p99 latency target of 120 ms. Its availability target is 99.95 percent. Synthetic checks call it from outside the data centre every minute. A runbook describes how to drain traffic from one region during an incident. Changes go through a canary release that receives five percent of traffic for thirty minutes. Error messages from it never include customer personal data. Its alerts page the owning team only during working hours unless an error budget is burning fast. It was last reviewed for security in the most recent annual audit.

### Support Desk

The Support Desk gives support agents one screen with a customer's orders, payments, and messages. The Support Desk is owned by the Customer team. The Support Desk depends on the Data Warehouse, the User Accounts, and the Refund Service.

It runs 2 replicas in the Mumbai region and is deployed weekly. The Support Desk has a p99 latency target of 35 ms. Its availability target is 99.9 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Error messages from it never include customer personal data. The team keeps a list of known failure modes and how each one was last fixed. Its dashboards show request rate, error rate, and saturation side by side. Synthetic checks call it from outside the data centre every minute. A runbook describes how to drain traffic from one region during an incident.

## Analytics services

### Clickstream Collector

The Clickstream Collector records page views and clicks from the website and apps. The Clickstream Collector is owned by the Analytics team. The Clickstream Collector depends on the Config Service.

It runs 6 replicas in the Frankfurt region and is deployed several times a day. The Clickstream Collector has a p99 latency target of 50 ms. Its availability target is 99.99 percent. The service writes structured logs that are kept for thirty days. A runbook describes how to drain traffic from one region during an incident. Capacity is reviewed every quarter against the traffic forecast. Synthetic checks call it from outside the data centre every minute. Its dashboards show request rate, error rate, and saturation side by side. Its alerts page the owning team only during working hours unless an error budget is burning fast.

### Experiment Platform

The Experiment Platform splits shoppers into groups to test changes and measures which version wins. The Experiment Platform is owned by the Analytics team. The Experiment Platform depends on the Permissions Service.

It runs 2 replicas in the Frankfurt region and is deployed daily. The Experiment Platform has a p99 latency target of 35 ms. Its availability target is 99.99 percent. Database migrations for it must be backwards compatible for one release. Its on-call rotation hands over every Monday at ten in the morning. The service writes structured logs that are kept for thirty days. Load tests run against it before every major sales event. Its dashboards show request rate, error rate, and saturation side by side. Capacity is reviewed every quarter against the traffic forecast.

### Forecasting Service

The Forecasting Service predicts next month's demand for each product so buyers can reorder in time. The Forecasting Service is owned by the Analytics team. The Forecasting Service depends on the Event Bus, the User Accounts, and the Pricing Engine.

It runs 4 replicas in the Singapore region and is deployed several times a day. The Forecasting Service has a p99 latency target of 150 ms. Its availability target is 99.95 percent. Its alerts page the owning team only during working hours unless an error budget is burning fast. Synthetic checks call it from outside the data centre every minute. Error messages from it never include customer personal data. Its on-call rotation hands over every Monday at ten in the morning. Capacity is reviewed every quarter against the traffic forecast. It exposes a health endpoint that the load balancer checks every ten seconds.

### Reporting Service

The Reporting Service builds the weekly sales and margin reports for the leadership team. The Reporting Service is owned by the Analytics team. The Reporting Service depends on the Token Service, the Product Catalog, and the Packing Service.

It runs 2 replicas in the Frankfurt region and is deployed weekly. The Reporting Service has a p99 latency target of 120 ms. Its availability target is 99.99 percent. Feature flags let the team switch new behaviour off without a deployment. All of its configuration is stored in version control and reviewed before release. Database migrations for it must be backwards compatible for one release. Synthetic checks call it from outside the data centre every minute. The service writes structured logs that are kept for thirty days. Its on-call rotation hands over every Monday at ten in the morning.

### Dashboard Service

The Dashboard Service shows live business numbers on screens in every office. The Dashboard Service is owned by the Analytics team. The Dashboard Service depends on the Payment Router.

It runs 2 replicas in the Frankfurt region and is deployed twice a week. The Dashboard Service has a p99 latency target of 250 ms. Its availability target is 99.99 percent. Its dashboards show request rate, error rate, and saturation side by side. The service writes structured logs that are kept for thirty days. All of its configuration is stored in version control and reviewed before release. Capacity is reviewed every quarter against the traffic forecast. A runbook describes how to drain traffic from one region during an incident. It was last reviewed for security in the most recent annual audit.

### Attribution Service

The Attribution Service works out which advert or campaign led to each sale. The Attribution Service is owned by the Analytics team. The Attribution Service depends on the Tax Calculator and the Checkout Orchestrator.

It runs 4 replicas in the Mumbai region and is deployed daily. The Attribution Service has a p99 latency target of 50 ms. Its availability target is 99.95 percent. All of its configuration is stored in version control and reviewed before release. Its dashboards show request rate, error rate, and saturation side by side. It was last reviewed for security in the most recent annual audit. It exposes a health endpoint that the load balancer checks every ten seconds. Its on-call rotation hands over every Monday at ten in the morning. Capacity is reviewed every quarter against the traffic forecast.

## 4. Teams

### Platform team

The Platform team is led by Asha Raman. The team is based in Bengaluru and holds its planning review every Monday. New joiners are paired with a buddy for their first month.

### Data Platform team

The Data Platform team is led by Marcus Lee. The team is based in Pune and holds its planning review every Tuesday. New joiners are paired with a buddy for their first month.

### Security team

The Security team is led by Elena Petrova. The team is based in Hyderabad and holds its planning review every Wednesday. New joiners are paired with a buddy for their first month.

### Identity team

The Identity team is led by Daniel Okafor. The team is based in Chennai and holds its planning review every Thursday. New joiners are paired with a buddy for their first month.

### Catalog team

The Catalog team is led by Priya Nair. The team is based in Bengaluru and holds its planning review every Friday. New joiners are paired with a buddy for their first month.

### Checkout team

The Checkout team is led by Tomas Garcia. The team is based in Madrid and holds its planning review every Monday. New joiners are paired with a buddy for their first month.

### Payments team

The Payments team is led by Mei Chen. The team is based in Singapore and holds its planning review every Tuesday. New joiners are paired with a buddy for their first month.

### Fulfilment team

The Fulfilment team is led by Samuel Adeyemi. The team is based in Lagos and holds its planning review every Wednesday. New joiners are paired with a buddy for their first month.

### Customer team

The Customer team is led by Hannah Schmidt. The team is based in Berlin and holds its planning review every Thursday. New joiners are paired with a buddy for their first month.

### Analytics team

The Analytics team is led by Kenji Watanabe. The team is based in Tokyo and holds its planning review every Friday. New joiners are paired with a buddy for their first month.
