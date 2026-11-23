# Validator comparison: KoSIT vs Mustang

Run 2026-11-23T09:04:17+00:00 on repo commit `8bd6ee6ad417e378ea5d38c51b378ea0b828c2f0`, corpus commit `02d4b5684738cb2d9faac2cec6599dc0e86c16d5`.
Agreement = share of supported files where accept/reject matches the expectation.
Median ms: KoSIT = HTTP round trip to the running daemon; Mustang = one CLI run incl. JVM start.

Each validator cell: agreement | supported/files | false accept | false reject | median ms.
Mustang's own top-level summary reflects the XML part only; 'Mustang PDF+XML' also rejects on PDF/A errors.

| Subset | exp. invalid | KoSIT | Mustang (own summary) | Mustang PDF+XML |
|---|---|---|---|---|
| corpus:XML-Rechnung/CII | 0 | 77.8% · 27/27 · FA 0 · FR 6 · 24.5 ms | 92.6% · 27/27 · FA 0 · FR 2 · 4666.0 ms | 92.6% · 27/27 · FA 0 · FR 2 · 4666.0 ms |
| corpus:XML-Rechnung/FX | 0 | 90.9% · 22/26 · FA 0 · FR 2 · 6.4 ms | 92.3% · 26/26 · FA 0 · FR 2 · 7990.0 ms | 92.3% · 26/26 · FA 0 · FR 2 · 7990.0 ms |
| corpus:XML-Rechnung/UBL | 0 | 100.0% · 5/28 · FA 0 · FR 0 · 31.0 ms | 85.7% · 28/28 · FA 0 · FR 4 · 5507.0 ms | 85.7% · 28/28 · FA 0 · FR 4 · 5507.0 ms |
| corpus:ZUGFeRDv1/correct | 0 | n/a · 0/21 · FA 0 · FR 0 · n/a ms | 76.2% · 21/21 · FA 0 · FR 5 · 14765.0 ms | 71.4% · 21/21 · FA 0 · FR 6 · 14765.0 ms |
| corpus:ZUGFeRDv1/fail | 3 | n/a · 0/3 · FA 0 · FR 0 · n/a ms | 100.0% · 3/3 · FA 0 · FR 0 · 15228.0 ms | 100.0% · 3/3 · FA 0 · FR 0 · 15228.0 ms |
| corpus:ZUGFeRDv2/correct | 0 | 89.1% · 55/92 · FA 0 · FR 6 · 23.4 ms | 78.3% · 92/92 · FA 0 · FR 20 · 7602.0 ms | 77.2% · 92/92 · FA 0 · FR 21 · 7602.0 ms |
| corpus:ZUGFeRDv2/fail | 24 | 75.0% · 12/24 · FA 3 · FR 0 · 11.4 ms | 70.8% · 24/24 · FA 7 · FR 0 · 7491.0 ms | 75.0% · 24/24 · FA 6 · FR 0 · 7491.0 ms |
| generated:xrechnung_cii | 2 | 100.0% · 50/50 · FA 0 · FR 0 · 7.5 ms | 100.0% · 50/50 · FA 0 · FR 0 · 5146.0 ms | 100.0% · 50/50 · FA 0 · FR 0 · 5146.0 ms |
| generated:xrechnung_ubl | 0 | 100.0% · 52/52 · FA 0 · FR 0 · 7.8 ms | 98.1% · 52/52 · FA 0 · FR 1 · 6014.0 ms | 98.1% · 52/52 · FA 0 · FR 1 · 6014.0 ms |
| generated:zugferd | 0 | 100.0% · 66/66 · FA 0 · FR 0 · 6.0 ms | 100.0% · 66/66 · FA 0 · FR 0 · 7183.5 ms | 100.0% · 66/66 · FA 0 · FR 0 · 7183.5 ms |

## Generated files: rejections by label

| Label | n | KoSIT rejects | Mustang rejects |
|---|---|---|---|
| arithmetic_error:lines[].line_net_amount | 7 | 0 | 1 |
| arithmetic_error:totals.total_with_vat | 2 | 2 | 2 |
| changed_iban:payment.iban | 10 | 0 | 0 |
| clean | 33 | 0 | 0 |
| duplicate_invoice | 9 | 0 | 0 |
| expired_batch:lines[].best_before_date | 3 | 0 | 0 |
| extra_line | 7 | 0 | 0 |
| missing_line | 7 | 0 | 0 |
| missing_mandatory_field:buyer_reference | 2 | 0 | 0 |
| missing_mandatory_field:lines[].batch_number | 3 | 0 | 0 |
| missing_mandatory_field:lines[].serial_numbers | 4 | 0 | 0 |
| missing_mandatory_field:order_reference | 2 | 0 | 0 |
| no_goods_receipt | 6 | 0 | 0 |
| over_delivery | 7 | 0 | 0 |
| price_deviation | 21 | 0 | 0 |
| rounding | 8 | 0 | 0 |
| short_delivery | 20 | 0 | 0 |
| short_shelf_life:lines[].best_before_date | 4 | 0 | 0 |
| unit_mismatch:lines[].quantity | 2 | 0 | 0 |
| unit_mismatch:lines[].unit_code | 6 | 0 | 0 |
| wrong_vat_rate:lines[].vat_rate | 8 | 0 | 0 |
