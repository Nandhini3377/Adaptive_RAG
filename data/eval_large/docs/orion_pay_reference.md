# Orion Pay API Reference

## 1. Introduction

Orion Pay is the payment API used by Orion Retail and its marketplace sellers. This reference explains the policies every integration must follow, every error code the API can return, and every client setting. Client libraries are published for Python, Java, Go, and JavaScript. Merchants should store the request ID of every failed call for support. Field names are case sensitive and always use snake case. All requests use JSON over HTTPS, and every response carries a request ID.

## 2. Policies

### Idempotency

Every payment request must carry an idempotency key, and keys are remembered for 24 hours. Timestamps are always given in UTC using the ISO 8601 format. Test card numbers for every error case are listed in the sandbox guide. Breaking changes are announced at least six months in advance. All requests use JSON over HTTPS, and every response carries a request ID. Merchants should store the request ID of every failed call for support. The sandbox environment behaves like production but never moves real money. Client libraries are published for Python, Java, Go, and JavaScript. Each API version is supported for at least two years after release. Amounts are always sent as integers in the currency's minor unit.

Breaking changes are announced at least six months in advance. Client libraries are published for Python, Java, Go, and JavaScript. Timestamps are always given in UTC using the ISO 8601 format. Each API version is supported for at least two years after release. Test card numbers for every error case are listed in the sandbox guide. Amounts are always sent as integers in the currency's minor unit. All requests use JSON over HTTPS, and every response carries a request ID. Merchants can see each request and its response in the dashboard for ninety days.

### Retries

Clients should retry a failed request at most 5 times, with exponential backoff starting at 200 milliseconds. Field names are case sensitive and always use snake case. Timestamps are always given in UTC using the ISO 8601 format. Each API version is supported for at least two years after release. Test card numbers for every error case are listed in the sandbox guide. Client libraries are published for Python, Java, Go, and JavaScript. All requests use JSON over HTTPS, and every response carries a request ID. Merchants can see each request and its response in the dashboard for ninety days. Breaking changes are announced at least six months in advance. Merchants should store the request ID of every failed call for support.

Client libraries are published for Python, Java, Go, and JavaScript. Amounts are always sent as integers in the currency's minor unit. Field names are case sensitive and always use snake case. Breaking changes are announced at least six months in advance. The status page lists any incident that affects payment success rates. The sandbox environment behaves like production but never moves real money. Test card numbers for every error case are listed in the sandbox guide. Timestamps are always given in UTC using the ISO 8601 format.

### Rate limits

Each merchant may send up to 300 requests per second, and requests above that limit receive HTTP status 429. Breaking changes are announced at least six months in advance. Field names are case sensitive and always use snake case. The sandbox environment behaves like production but never moves real money. Amounts are always sent as integers in the currency's minor unit. Merchants can see each request and its response in the dashboard for ninety days. The status page lists any incident that affects payment success rates. Client libraries are published for Python, Java, Go, and JavaScript. Each API version is supported for at least two years after release. All requests use JSON over HTTPS, and every response carries a request ID.

The status page lists any incident that affects payment success rates. Merchants can see each request and its response in the dashboard for ninety days. Timestamps are always given in UTC using the ISO 8601 format. All requests use JSON over HTTPS, and every response carries a request ID. Client libraries are published for Python, Java, Go, and JavaScript. Merchants should store the request ID of every failed call for support. Breaking changes are announced at least six months in advance. The sandbox environment behaves like production but never moves real money.

### Webhooks

Webhook deliveries that fail are retried with backoff for up to 3 days. Timestamps are always given in UTC using the ISO 8601 format. All requests use JSON over HTTPS, and every response carries a request ID. Test card numbers for every error case are listed in the sandbox guide. Merchants can see each request and its response in the dashboard for ninety days. Field names are case sensitive and always use snake case. Client libraries are published for Python, Java, Go, and JavaScript. Each API version is supported for at least two years after release. Merchants should store the request ID of every failed call for support. The status page lists any incident that affects payment success rates.

The sandbox environment behaves like production but never moves real money. Merchants can see each request and its response in the dashboard for ninety days. Each API version is supported for at least two years after release. Client libraries are published for Python, Java, Go, and JavaScript. Test card numbers for every error case are listed in the sandbox guide. The status page lists any incident that affects payment success rates. Breaking changes are announced at least six months in advance. Merchants should store the request ID of every failed call for support.

### Data retention

Raw card numbers are never stored, and tokenized card data is deleted 13 months after the card was last used. All requests use JSON over HTTPS, and every response carries a request ID. Breaking changes are announced at least six months in advance. Timestamps are always given in UTC using the ISO 8601 format. Each API version is supported for at least two years after release. Merchants should store the request ID of every failed call for support. Client libraries are published for Python, Java, Go, and JavaScript. The sandbox environment behaves like production but never moves real money. Field names are case sensitive and always use snake case. Test card numbers for every error case are listed in the sandbox guide.

The sandbox environment behaves like production but never moves real money. Breaking changes are announced at least six months in advance. Field names are case sensitive and always use snake case. Each API version is supported for at least two years after release. Timestamps are always given in UTC using the ISO 8601 format. All requests use JSON over HTTPS, and every response carries a request ID. Test card numbers for every error case are listed in the sandbox guide. The status page lists any incident that affects payment success rates.

### Settlement

Settlement batches close at 23:00 UTC every day, and funds reach merchants within 2 business days. Timestamps are always given in UTC using the ISO 8601 format. Each API version is supported for at least two years after release. Breaking changes are announced at least six months in advance. Field names are case sensitive and always use snake case. The sandbox environment behaves like production but never moves real money. All requests use JSON over HTTPS, and every response carries a request ID. Test card numbers for every error case are listed in the sandbox guide. Client libraries are published for Python, Java, Go, and JavaScript. Amounts are always sent as integers in the currency's minor unit.

Each API version is supported for at least two years after release. Merchants should store the request ID of every failed call for support. Amounts are always sent as integers in the currency's minor unit. Client libraries are published for Python, Java, Go, and JavaScript. Field names are case sensitive and always use snake case. Merchants can see each request and its response in the dashboard for ninety days. The status page lists any incident that affects payment success rates. Test card numbers for every error case are listed in the sandbox guide.

### Refunds

Refunds can be issued up to 180 days after the original payment. All requests use JSON over HTTPS, and every response carries a request ID. Test card numbers for every error case are listed in the sandbox guide. Timestamps are always given in UTC using the ISO 8601 format. Client libraries are published for Python, Java, Go, and JavaScript. The status page lists any incident that affects payment success rates. Field names are case sensitive and always use snake case. Merchants should store the request ID of every failed call for support. Amounts are always sent as integers in the currency's minor unit. Each API version is supported for at least two years after release.

The sandbox environment behaves like production but never moves real money. All requests use JSON over HTTPS, and every response carries a request ID. Breaking changes are announced at least six months in advance. Client libraries are published for Python, Java, Go, and JavaScript. Field names are case sensitive and always use snake case. The status page lists any incident that affects payment success rates. Merchants can see each request and its response in the dashboard for ninety days. Each API version is supported for at least two years after release.

### Disputes

Merchants have 7 days to respond to a chargeback with supporting evidence. Breaking changes are announced at least six months in advance. Each API version is supported for at least two years after release. The status page lists any incident that affects payment success rates. All requests use JSON over HTTPS, and every response carries a request ID. Field names are case sensitive and always use snake case. Test card numbers for every error case are listed in the sandbox guide. Timestamps are always given in UTC using the ISO 8601 format. Merchants can see each request and its response in the dashboard for ninety days. Amounts are always sent as integers in the currency's minor unit.

Breaking changes are announced at least six months in advance. All requests use JSON over HTTPS, and every response carries a request ID. The status page lists any incident that affects payment success rates. The sandbox environment behaves like production but never moves real money. Test card numbers for every error case are listed in the sandbox guide. Timestamps are always given in UTC using the ISO 8601 format. Merchants should store the request ID of every failed call for support. Amounts are always sent as integers in the currency's minor unit.

## 3. Error codes

### Errors about card number

Error PAY-1104 means the card number is missing from the request. It can appear when a request is replayed from a log file. It is logged with the request ID so support can trace it. To resolve it, add the field and send the request again. In the sandbox, request req_7e544d56 reproduces PAY-1104 on demand.

Error PAY-0107 means the card number has the wrong format. It can appear when a request is replayed from a log file. It is most often seen right after a merchant changes their integration. To resolve it, check the format in the field reference and resend. In the sandbox, request req_3c73d5f4 reproduces PAY-0107 on demand.

Error PAY-0711 means the card number has expired. Support tickets show it is common during large sales events. It can appear when a request is replayed from a log file. To resolve it, ask the customer for fresh details. In the sandbox, request req_32830689 reproduces PAY-0711 on demand.

Error PAY-4000 means the card number does not match the stored value. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_6862bf79 reproduces PAY-4000 on demand.

Error PAY-7417 means the card number was rejected by the card network. It is logged with the request ID so support can trace it. This usually comes from an outdated client library. To resolve it, show the customer a generic decline message. In the sandbox, request req_8b6bfeae reproduces PAY-7417 on demand.

Error PAY-7077 means the card number is longer than allowed. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_e22b64a6 reproduces PAY-7077 on demand.

Error PAY-1777 means the card number belongs to a different merchant. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_9fe5e399 reproduces PAY-1777 on demand.

Error PAY-4070 means the card number was already used. It is most often seen right after a merchant changes their integration. This usually comes from an outdated client library. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_6bca9b3f reproduces PAY-4070 on demand.

Error PAY-0740 means the card number is locked for manual review. It is logged with the request ID so support can trace it. It can appear when a request is replayed from a log file. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_2c564d56 reproduces PAY-0740 on demand.

Error PAY-1707 means the card number timed out before it could be checked. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, retry with exponential backoff. In the sandbox, request req_c272f5a7 reproduces PAY-1707 on demand.

### Errors about expiry date

Error PAY-7440 means the expiry date is missing from the request. Support tickets show it is common during large sales events. It is logged with the request ID so support can trace it. To resolve it, add the field and send the request again. In the sandbox, request req_4485c04f reproduces PAY-7440 on demand.

Error PAY-1111 means the expiry date has the wrong format. Support tickets show it is common during large sales events. It is logged with the request ID so support can trace it. To resolve it, check the format in the field reference and resend. In the sandbox, request req_32fe1f36 reproduces PAY-1111 on demand.

Error PAY-7004 means the expiry date has expired. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, ask the customer for fresh details. In the sandbox, request req_3ece9f2c reproduces PAY-7004 on demand.

Error PAY-7714 means the expiry date does not match the stored value. It is most often seen right after a merchant changes their integration. Support tickets show it is common during large sales events. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_940a3537 reproduces PAY-7714 on demand.

Error PAY-1471 means the expiry date was rejected by the card network. Support tickets show it is common during large sales events. This usually comes from an outdated client library. To resolve it, show the customer a generic decline message. In the sandbox, request req_6564d134 reproduces PAY-1471 on demand.

Error PAY-0407 means the expiry date is longer than allowed. It is most often seen right after a merchant changes their integration. Mobile clients on weak connections trigger it more often than web clients. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_86bc2b99 reproduces PAY-0407 on demand.

Error PAY-7740 means the expiry date belongs to a different merchant. It is logged with the request ID so support can trace it. This usually comes from an outdated client library. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_a74068b2 reproduces PAY-7740 on demand.

Error PAY-0701 means the expiry date was already used. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_012664f6 reproduces PAY-0701 on demand.

Error PAY-0774 means the expiry date is locked for manual review. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_ea14843a reproduces PAY-0774 on demand.

Error PAY-0117 means the expiry date timed out before it could be checked. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, retry with exponential backoff. In the sandbox, request req_3b9edacb reproduces PAY-0117 on demand.

### Errors about card security code

Error PAY-0470 means the card security code is missing from the request. This usually comes from an outdated client library. It is most often seen right after a merchant changes their integration. To resolve it, add the field and send the request again. In the sandbox, request req_133ad73d reproduces PAY-0470 on demand.

Error PAY-1117 means the card security code has the wrong format. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, check the format in the field reference and resend. In the sandbox, request req_f2198825 reproduces PAY-1117 on demand.

Error PAY-4074 means the card security code has expired. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, ask the customer for fresh details. In the sandbox, request req_5985ea3f reproduces PAY-4074 on demand.

Error PAY-7470 means the card security code does not match the stored value. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_570b534d reproduces PAY-7470 on demand.

Error PAY-1101 means the card security code was rejected by the card network. This usually comes from an outdated client library. It is most often seen right after a merchant changes their integration. To resolve it, show the customer a generic decline message. In the sandbox, request req_fff7ba0d reproduces PAY-1101 on demand.

Error PAY-0771 means the card security code is longer than allowed. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_e9f8f71f reproduces PAY-0771 on demand.

Error PAY-1174 means the card security code belongs to a different merchant. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_5f2ee40d reproduces PAY-1174 on demand.

Error PAY-1004 means the card security code was already used. Mobile clients on weak connections trigger it more often than web clients. Support tickets show it is common during large sales events. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_13f38870 reproduces PAY-1004 on demand.

Error PAY-7744 means the card security code is locked for manual review. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_8c4caa83 reproduces PAY-7744 on demand.

Error PAY-4101 means the card security code timed out before it could be checked. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, retry with exponential backoff. In the sandbox, request req_8cd5d187 reproduces PAY-4101 on demand.

### Errors about billing address

Error PAY-0707 means the billing address is missing from the request. It is logged with the request ID so support can trace it. Mobile clients on weak connections trigger it more often than web clients. To resolve it, add the field and send the request again. In the sandbox, request req_29e78b06 reproduces PAY-0707 on demand.

Error PAY-0011 means the billing address has the wrong format. It is logged with the request ID so support can trace it. Support tickets show it is common during large sales events. To resolve it, check the format in the field reference and resend. In the sandbox, request req_4ebe9880 reproduces PAY-0011 on demand.

Error PAY-4777 means the billing address has expired. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, ask the customer for fresh details. In the sandbox, request req_e239d3d7 reproduces PAY-4777 on demand.

Error PAY-7174 means the billing address does not match the stored value. It can appear when a request is replayed from a log file. It is logged with the request ID so support can trace it. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_cd5e4aa0 reproduces PAY-7174 on demand.

Error PAY-1441 means the billing address was rejected by the card network. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, show the customer a generic decline message. In the sandbox, request req_67ac56f8 reproduces PAY-1441 on demand.

Error PAY-1404 means the billing address is longer than allowed. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_e6d14318 reproduces PAY-1404 on demand.

Error PAY-7171 means the billing address belongs to a different merchant. It can appear when a request is replayed from a log file. This usually comes from an outdated client library. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_d203acfe reproduces PAY-7171 on demand.

Error PAY-4774 means the billing address was already used. It can appear when a request is replayed from a log file. Mobile clients on weak connections trigger it more often than web clients. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_e201aafd reproduces PAY-4774 on demand.

Error PAY-4014 means the billing address is locked for manual review. It can appear when a request is replayed from a log file. It is most often seen right after a merchant changes their integration. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_21460c5a reproduces PAY-4014 on demand.

Error PAY-7771 means the billing address timed out before it could be checked. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, retry with exponential backoff. In the sandbox, request req_658f62d1 reproduces PAY-7771 on demand.

### Errors about currency code

Error PAY-1400 means the currency code is missing from the request. Mobile clients on weak connections trigger it more often than web clients. It is logged with the request ID so support can trace it. To resolve it, add the field and send the request again. In the sandbox, request req_ed5ec904 reproduces PAY-1400 on demand.

Error PAY-1011 means the currency code has the wrong format. It is logged with the request ID so support can trace it. Mobile clients on weak connections trigger it more often than web clients. To resolve it, check the format in the field reference and resend. In the sandbox, request req_2bf39775 reproduces PAY-1011 on demand.

Error PAY-1114 means the currency code has expired. Support tickets show it is common during large sales events. It is logged with the request ID so support can trace it. To resolve it, ask the customer for fresh details. In the sandbox, request req_112d4095 reproduces PAY-1114 on demand.

Error PAY-7000 means the currency code does not match the stored value. It can appear when a request is replayed from a log file. It is logged with the request ID so support can trace it. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_ce017551 reproduces PAY-7000 on demand.

Error PAY-0077 means the currency code was rejected by the card network. Support tickets show it is common during large sales events. It is most often seen right after a merchant changes their integration. To resolve it, show the customer a generic decline message. In the sandbox, request req_e9ad2bc7 reproduces PAY-0077 on demand.

Error PAY-7741 means the currency code is longer than allowed. Support tickets show it is common during large sales events. This usually comes from an outdated client library. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_a2e8fec0 reproduces PAY-7741 on demand.

Error PAY-1017 means the currency code belongs to a different merchant. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_e4219307 reproduces PAY-1017 on demand.

Error PAY-4107 means the currency code was already used. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_9efd55d2 reproduces PAY-4107 on demand.

Error PAY-1170 means the currency code is locked for manual review. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_d445a53e reproduces PAY-1170 on demand.

Error PAY-0400 means the currency code timed out before it could be checked. It is most often seen right after a merchant changes their integration. Mobile clients on weak connections trigger it more often than web clients. To resolve it, retry with exponential backoff. In the sandbox, request req_37d7d190 reproduces PAY-0400 on demand.

### Errors about merchant account

Error PAY-4477 means the merchant account is missing from the request. It can appear when a request is replayed from a log file. Mobile clients on weak connections trigger it more often than web clients. To resolve it, add the field and send the request again. In the sandbox, request req_280f005d reproduces PAY-4477 on demand.

Error PAY-7770 means the merchant account has the wrong format. Support tickets show it is common during large sales events. This usually comes from an outdated client library. To resolve it, check the format in the field reference and resend. In the sandbox, request req_26437a8e reproduces PAY-7770 on demand.

Error PAY-4017 means the merchant account has expired. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, ask the customer for fresh details. In the sandbox, request req_d6948ded reproduces PAY-4017 on demand.

Error PAY-4401 means the merchant account does not match the stored value. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_997a20be reproduces PAY-4401 on demand.

Error PAY-0717 means the merchant account was rejected by the card network. Mobile clients on weak connections trigger it more often than web clients. Support tickets show it is common during large sales events. To resolve it, show the customer a generic decline message. In the sandbox, request req_a626b097 reproduces PAY-0717 on demand.

Error PAY-7711 means the merchant account is longer than allowed. Support tickets show it is common during large sales events. Mobile clients on weak connections trigger it more often than web clients. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_3fcf6d85 reproduces PAY-7711 on demand.

Error PAY-7114 means the merchant account belongs to a different merchant. It can appear when a request is replayed from a log file. Support tickets show it is common during large sales events. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_7037e034 reproduces PAY-7114 on demand.

Error PAY-0777 means the merchant account was already used. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_7d4ffa0f reproduces PAY-0777 on demand.

Error PAY-7170 means the merchant account is locked for manual review. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_7924dede reproduces PAY-7170 on demand.

Error PAY-1414 means the merchant account timed out before it could be checked. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, retry with exponential backoff. In the sandbox, request req_20e27c17 reproduces PAY-1414 on demand.

### Errors about idempotency key

Error PAY-4411 means the idempotency key is missing from the request. It can appear when a request is replayed from a log file. Support tickets show it is common during large sales events. To resolve it, add the field and send the request again. In the sandbox, request req_0a6fb154 reproduces PAY-4411 on demand.

Error PAY-1704 means the idempotency key has the wrong format. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, check the format in the field reference and resend. In the sandbox, request req_bbc55c33 reproduces PAY-1704 on demand.

Error PAY-1474 means the idempotency key has expired. It is logged with the request ID so support can trace it. Mobile clients on weak connections trigger it more often than web clients. To resolve it, ask the customer for fresh details. In the sandbox, request req_1478c7b9 reproduces PAY-1474 on demand.

Error PAY-1077 means the idempotency key does not match the stored value. Mobile clients on weak connections trigger it more often than web clients. It can appear when a request is replayed from a log file. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_c8c42276 reproduces PAY-1077 on demand.

Error PAY-7400 means the idempotency key was rejected by the card network. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, show the customer a generic decline message. In the sandbox, request req_d0a32611 reproduces PAY-7400 on demand.

Error PAY-7074 means the idempotency key is longer than allowed. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_7deb30ad reproduces PAY-7074 on demand.

Error PAY-0040 means the idempotency key belongs to a different merchant. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_c194ff53 reproduces PAY-0040 on demand.

Error PAY-1470 means the idempotency key was already used. It is most often seen right after a merchant changes their integration. Support tickets show it is common during large sales events. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_d0cce893 reproduces PAY-1470 on demand.

Error PAY-4711 means the idempotency key is locked for manual review. It is most often seen right after a merchant changes their integration. Support tickets show it is common during large sales events. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_eb7f1414 reproduces PAY-4711 on demand.

Error PAY-1741 means the idempotency key timed out before it could be checked. It is most often seen right after a merchant changes their integration. Mobile clients on weak connections trigger it more often than web clients. To resolve it, retry with exponential backoff. In the sandbox, request req_8189ac45 reproduces PAY-1741 on demand.

### Errors about webhook signature

Error PAY-4114 means the webhook signature is missing from the request. Support tickets show it is common during large sales events. It is logged with the request ID so support can trace it. To resolve it, add the field and send the request again. In the sandbox, request req_096de421 reproduces PAY-4114 on demand.

Error PAY-1771 means the webhook signature has the wrong format. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, check the format in the field reference and resend. In the sandbox, request req_efb82825 reproduces PAY-1771 on demand.

Error PAY-0000 means the webhook signature has expired. It is logged with the request ID so support can trace it. Support tickets show it is common during large sales events. To resolve it, ask the customer for fresh details. In the sandbox, request req_e539cb16 reproduces PAY-0000 on demand.

Error PAY-0104 means the webhook signature does not match the stored value. It is most often seen right after a merchant changes their integration. Support tickets show it is common during large sales events. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_87dd58d9 reproduces PAY-0104 on demand.

Error PAY-1410 means the webhook signature was rejected by the card network. It is logged with the request ID so support can trace it. Support tickets show it is common during large sales events. To resolve it, show the customer a generic decline message. In the sandbox, request req_e566e133 reproduces PAY-1410 on demand.

Error PAY-7047 means the webhook signature is longer than allowed. Support tickets show it is common during large sales events. Mobile clients on weak connections trigger it more often than web clients. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_cc342416 reproduces PAY-7047 on demand.

Error PAY-1717 means the webhook signature belongs to a different merchant. Support tickets show it is common during large sales events. It can appear when a request is replayed from a log file. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_fd914b0e reproduces PAY-1717 on demand.

Error PAY-7707 means the webhook signature was already used. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_5c396f5e reproduces PAY-7707 on demand.

Error PAY-7014 means the webhook signature is locked for manual review. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_3ae46155 reproduces PAY-7014 on demand.

Error PAY-0147 means the webhook signature timed out before it could be checked. Mobile clients on weak connections trigger it more often than web clients. This usually comes from an outdated client library. To resolve it, retry with exponential backoff. In the sandbox, request req_841f92ca reproduces PAY-0147 on demand.

### Errors about refund amount

Error PAY-0741 means the refund amount is missing from the request. Support tickets show it is common during large sales events. Mobile clients on weak connections trigger it more often than web clients. To resolve it, add the field and send the request again. In the sandbox, request req_e54e19e5 reproduces PAY-0741 on demand.

Error PAY-0417 means the refund amount has the wrong format. It is logged with the request ID so support can trace it. This usually comes from an outdated client library. To resolve it, check the format in the field reference and resend. In the sandbox, request req_bf433e03 reproduces PAY-0417 on demand.

Error PAY-0414 means the refund amount has expired. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, ask the customer for fresh details. In the sandbox, request req_a0288056 reproduces PAY-0414 on demand.

Error PAY-4011 means the refund amount does not match the stored value. It can appear when a request is replayed from a log file. Mobile clients on weak connections trigger it more often than web clients. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_0c3b1266 reproduces PAY-4011 on demand.

Error PAY-4700 means the refund amount was rejected by the card network. It can appear when a request is replayed from a log file. It is most often seen right after a merchant changes their integration. To resolve it, show the customer a generic decline message. In the sandbox, request req_0bab5f9f reproduces PAY-4700 on demand.

Error PAY-7007 means the refund amount is longer than allowed. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_912eda41 reproduces PAY-7007 on demand.

Error PAY-1711 means the refund amount belongs to a different merchant. Support tickets show it is common during large sales events. This usually comes from an outdated client library. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_85e9251c reproduces PAY-1711 on demand.

Error PAY-0111 means the refund amount was already used. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_223be9e7 reproduces PAY-0111 on demand.

Error PAY-4071 means the refund amount is locked for manual review. Support tickets show it is common during large sales events. Mobile clients on weak connections trigger it more often than web clients. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_d416b8a9 reproduces PAY-4071 on demand.

Error PAY-0044 means the refund amount timed out before it could be checked. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, retry with exponential backoff. In the sandbox, request req_cd2f4934 reproduces PAY-0044 on demand.

### Errors about settlement batch

Error PAY-4717 means the settlement batch is missing from the request. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, add the field and send the request again. In the sandbox, request req_736b1be2 reproduces PAY-4717 on demand.

Error PAY-7144 means the settlement batch has the wrong format. This usually comes from an outdated client library. It is most often seen right after a merchant changes their integration. To resolve it, check the format in the field reference and resend. In the sandbox, request req_c83b6269 reproduces PAY-7144 on demand.

Error PAY-0747 means the settlement batch has expired. It can appear when a request is replayed from a log file. Support tickets show it is common during large sales events. To resolve it, ask the customer for fresh details. In the sandbox, request req_f7962f83 reproduces PAY-0747 on demand.

Error PAY-7404 means the settlement batch does not match the stored value. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_e486737d reproduces PAY-7404 on demand.

Error PAY-0041 means the settlement batch was rejected by the card network. Mobile clients on weak connections trigger it more often than web clients. It is logged with the request ID so support can trace it. To resolve it, show the customer a generic decline message. In the sandbox, request req_bbc81f54 reproduces PAY-0041 on demand.

Error PAY-1071 means the settlement batch is longer than allowed. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_e74c00f4 reproduces PAY-1071 on demand.

Error PAY-4410 means the settlement batch belongs to a different merchant. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_88122e14 reproduces PAY-4410 on demand.

Error PAY-1000 means the settlement batch was already used. It can appear when a request is replayed from a log file. It is most often seen right after a merchant changes their integration. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_3cd7dcef reproduces PAY-1000 on demand.

Error PAY-4710 means the settlement batch is locked for manual review. This usually comes from an outdated client library. It is logged with the request ID so support can trace it. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_f0e02c42 reproduces PAY-4710 on demand.

Error PAY-1477 means the settlement batch timed out before it could be checked. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, retry with exponential backoff. In the sandbox, request req_a43dede7 reproduces PAY-1477 on demand.

### Errors about customer token

Error PAY-0170 means the customer token is missing from the request. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, add the field and send the request again. In the sandbox, request req_823209b5 reproduces PAY-0170 on demand.

Error PAY-0141 means the customer token has the wrong format. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, check the format in the field reference and resend. In the sandbox, request req_a03f2a2b reproduces PAY-0141 on demand.

Error PAY-4714 means the customer token has expired. It is logged with the request ID so support can trace it. It can appear when a request is replayed from a log file. To resolve it, ask the customer for fresh details. In the sandbox, request req_01a01d42 reproduces PAY-4714 on demand.

Error PAY-1070 means the customer token does not match the stored value. It can appear when a request is replayed from a log file. It is logged with the request ID so support can trace it. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_a7d0e597 reproduces PAY-1070 on demand.

Error PAY-7141 means the customer token was rejected by the card network. It is most often seen right after a merchant changes their integration. It is logged with the request ID so support can trace it. To resolve it, show the customer a generic decline message. In the sandbox, request req_ff21dd5a reproduces PAY-7141 on demand.

Error PAY-4111 means the customer token is longer than allowed. Support tickets show it is common during large sales events. It is most often seen right after a merchant changes their integration. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_a4de7a8d reproduces PAY-4111 on demand.

Error PAY-7474 means the customer token belongs to a different merchant. This usually comes from an outdated client library. Support tickets show it is common during large sales events. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_0d72cb97 reproduces PAY-7474 on demand.

Error PAY-1407 means the customer token was already used. It is logged with the request ID so support can trace it. Mobile clients on weak connections trigger it more often than web clients. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_ade25655 reproduces PAY-1407 on demand.

Error PAY-7410 means the customer token is locked for manual review. It is logged with the request ID so support can trace it. Mobile clients on weak connections trigger it more often than web clients. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_f8cde59b reproduces PAY-7410 on demand.

Error PAY-7071 means the customer token timed out before it could be checked. Support tickets show it is common during large sales events. It is most often seen right after a merchant changes their integration. To resolve it, retry with exponential backoff. In the sandbox, request req_81e6d6c8 reproduces PAY-7071 on demand.

### Errors about 3-D Secure challenge

Error PAY-4444 means the 3-D Secure challenge is missing from the request. It is most often seen right after a merchant changes their integration. Support tickets show it is common during large sales events. To resolve it, add the field and send the request again. In the sandbox, request req_e79a95aa reproduces PAY-4444 on demand.

Error PAY-0004 means the 3-D Secure challenge has the wrong format. It is logged with the request ID so support can trace it. It is most often seen right after a merchant changes their integration. To resolve it, check the format in the field reference and resend. In the sandbox, request req_f1d7b8aa reproduces PAY-0004 on demand.

Error PAY-4041 means the 3-D Secure challenge has expired. It is logged with the request ID so support can trace it. Support tickets show it is common during large sales events. To resolve it, ask the customer for fresh details. In the sandbox, request req_63825046 reproduces PAY-4041 on demand.

Error PAY-4400 means the 3-D Secure challenge does not match the stored value. Mobile clients on weak connections trigger it more often than web clients. It is most often seen right after a merchant changes their integration. To resolve it, reload the stored value and compare before resending. In the sandbox, request req_894e9f37 reproduces PAY-4400 on demand.

Error PAY-4441 means the 3-D Secure challenge was rejected by the card network. It can appear when a request is replayed from a log file. Mobile clients on weak connections trigger it more often than web clients. To resolve it, show the customer a generic decline message. In the sandbox, request req_b2971b77 reproduces PAY-4441 on demand.

Error PAY-7101 means the 3-D Secure challenge is longer than allowed. This usually comes from an outdated client library. It can appear when a request is replayed from a log file. To resolve it, shorten the value to the documented maximum. In the sandbox, request req_e27f8be8 reproduces PAY-7101 on demand.

Error PAY-1100 means the 3-D Secure challenge belongs to a different merchant. It is most often seen right after a merchant changes their integration. It can appear when a request is replayed from a log file. To resolve it, use the credentials of the merchant that owns it. In the sandbox, request req_e9298400 reproduces PAY-1100 on demand.

Error PAY-7471 means the 3-D Secure challenge was already used. It is most often seen right after a merchant changes their integration. This usually comes from an outdated client library. To resolve it, create a new one instead of reusing the old one. In the sandbox, request req_06e315e3 reproduces PAY-7471 on demand.

Error PAY-4744 means the 3-D Secure challenge is locked for manual review. This usually comes from an outdated client library. Mobile clients on weak connections trigger it more often than web clients. To resolve it, wait for the review to finish before retrying. In the sandbox, request req_edcf975c reproduces PAY-4744 on demand.

Error PAY-4117 means the 3-D Secure challenge timed out before it could be checked. Support tickets show it is common during large sales events. It is most often seen right after a merchant changes their integration. To resolve it, retry with exponential backoff. In the sandbox, request req_b363af43 reproduces PAY-4117 on demand.

## 4. Client settings

The setting retry_max_attempts controls how many times the client library retries a failed request and defaults to 5. All requests use JSON over HTTPS, and every response carries a request ID. Field names are case sensitive and always use snake case.

The setting retry_backoff_ms controls the first wait between retries, which doubles each time and defaults to 200. Merchants can see each request and its response in the dashboard for ninety days. Test card numbers for every error case are listed in the sandbox guide.

The setting retry_backoff_max_ms controls the longest wait allowed between two retries and defaults to 10000. Test card numbers for every error case are listed in the sandbox guide. All requests use JSON over HTTPS, and every response carries a request ID.

The setting request_timeout_ms controls how long the client waits for any response and defaults to 30000. Field names are case sensitive and always use snake case. The sandbox environment behaves like production but never moves real money.

The setting connect_timeout_ms controls how long the client waits to open a connection and defaults to 5000. Field names are case sensitive and always use snake case. All requests use JSON over HTTPS, and every response carries a request ID.

The setting webhook_retry_hours controls how long failed webhook deliveries keep being retried and defaults to 72. The sandbox environment behaves like production but never moves real money. The status page lists any incident that affects payment success rates.

The setting webhook_timeout_ms controls how long Orion Pay waits for a merchant's webhook endpoint and defaults to 10000. Each API version is supported for at least two years after release. Client libraries are published for Python, Java, Go, and JavaScript.

The setting webhook_batch_size controls how many events are sent in one webhook call and defaults to 50. Merchants should store the request ID of every failed call for support. Test card numbers for every error case are listed in the sandbox guide.

The setting idempotency_ttl_hours controls how long an idempotency key is remembered and defaults to 24. The sandbox environment behaves like production but never moves real money. Timestamps are always given in UTC using the ISO 8601 format.

The setting settlement_cutoff_utc controls the time each daily settlement batch closes and defaults to 23:00. The sandbox environment behaves like production but never moves real money. Client libraries are published for Python, Java, Go, and JavaScript.

The setting settlement_delay_days controls how many business days settled funds take to arrive and defaults to 2. Client libraries are published for Python, Java, Go, and JavaScript. Field names are case sensitive and always use snake case.

The setting refund_window_days controls how long after a payment a refund can be issued and defaults to 180. The sandbox environment behaves like production but never moves real money. All requests use JSON over HTTPS, and every response carries a request ID.

The setting refund_partial_limit controls how many partial refunds one payment can have and defaults to 10. All requests use JSON over HTTPS, and every response carries a request ID. Test card numbers for every error case are listed in the sandbox guide.

The setting dispute_response_days controls how long a merchant has to answer a chargeback and defaults to 7. The sandbox environment behaves like production but never moves real money. Test card numbers for every error case are listed in the sandbox guide.

The setting fraud_score_threshold controls the fraud score above which a payment is held and defaults to 0.85. Test card numbers for every error case are listed in the sandbox guide. Breaking changes are announced at least six months in advance.

The setting fraud_review_hours controls how long a held payment waits for manual review and defaults to 48. Amounts are always sent as integers in the currency's minor unit. The sandbox environment behaves like production but never moves real money.

The setting token_ttl_days controls how long a saved card token stays valid without use and defaults to 395. Merchants can see each request and its response in the dashboard for ninety days. The sandbox environment behaves like production but never moves real money.

The setting token_cache_size controls how many card tokens the client library caches and defaults to 1000. Test card numbers for every error case are listed in the sandbox guide. Client libraries are published for Python, Java, Go, and JavaScript.

The setting rate_limit_rps controls how many requests per second one merchant may send and defaults to 300. Breaking changes are announced at least six months in advance. Each API version is supported for at least two years after release.

The setting rate_limit_burst controls how many extra requests are allowed in a short burst and defaults to 600. Each API version is supported for at least two years after release. Timestamps are always given in UTC using the ISO 8601 format.

The setting batch_export_rows controls the maximum number of rows in one transaction export and defaults to 100000. Breaking changes are announced at least six months in advance. All requests use JSON over HTTPS, and every response carries a request ID.

The setting batch_export_format controls the default file format of transaction exports and defaults to CSV. Each API version is supported for at least two years after release. Breaking changes are announced at least six months in advance.

The setting currency_rate_refresh_min controls how often exchange rates are refreshed and defaults to 15. Breaking changes are announced at least six months in advance. All requests use JSON over HTTPS, and every response carries a request ID.

The setting currency_default controls the currency used when a merchant sets none and defaults to INR. Field names are case sensitive and always use snake case. Each API version is supported for at least two years after release.

The setting card_min_amount controls the smallest card payment accepted, in minor units and defaults to 100. Each API version is supported for at least two years after release. The status page lists any incident that affects payment success rates.

The setting card_max_amount controls the largest card payment accepted without review, in minor units and defaults to 50000000. Merchants should store the request ID of every failed call for support. Amounts are always sent as integers in the currency's minor unit.

The setting three_ds_required_above controls the amount above which 3-D Secure is always required and defaults to 500000. Breaking changes are announced at least six months in advance. The status page lists any incident that affects payment success rates.

The setting log_retention_days controls how long request logs are kept and defaults to 90. Field names are case sensitive and always use snake case. All requests use JSON over HTTPS, and every response carries a request ID.

The setting log_redact_fields controls whether sensitive fields are masked in logs and defaults to true. Timestamps are always given in UTC using the ISO 8601 format. All requests use JSON over HTTPS, and every response carries a request ID.

The setting sandbox_reset_days controls how often sandbox accounts are wiped and defaults to 30. Timestamps are always given in UTC using the ISO 8601 format. Merchants should store the request ID of every failed call for support.
