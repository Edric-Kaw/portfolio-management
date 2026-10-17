| Header                   | Description                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| **ReportingDate**        | The actual reporting date of the record, usually in full date format. Example: `2026-06-30`                    |
| **ReportingDate_YYYYMM** | Reporting period in year and month format. Example: `202606`                                                   |
| **ReportingDate_YYYYQQ** | Reporting period in year and quarter format. Example: `2026Q2`                                                 |
| **Type**                 | Main classification of the financial item, such as asset, liability, cash, investment, loan, or deposit.       |
| **Category**             | The broader category of the account or financial item. Example: Bank Account, Fixed Deposit, Investment, Loan. |
| **SubCategory**          | More detailed classification under the category. Example: Savings Account, Current Account, FD 12 Months.      |
| **Account**              | The name or identifier of the account, bank, investment, or financial product.                                 |
| **Currency**             | The original currency of the balance. Example: `MYR`, `USD`, `SGD`.                                            |
| **Balance**              | The account balance in the original currency.                                                                  |
| **BalanceInMYR**         | The converted balance amount in Malaysian Ringgit.                                                             |
| **MaturityDate**         | The date when the financial product matures, mainly for fixed deposits, bonds, or term investments.            |
| **InterestRate**         | The applicable interest rate or return rate for the account/product.                                           |
| **CashLiquidity**        | Indicates how easily the balance can be converted into cash or withdrawn. Example: Very High, High, Medium, Low. CashLiquidity is determined based on the category, subcategory, account type, and maturity period, where Cash & Cash Equivalent with no maturity date or maturity within 1–3 days is classified as Very High, 4–30 days as High, 31–90 days as Medium, and more than 90 days as Low; Retirement Fund is classified as Low, Money Market Fund as High, while Equity and Investment Fund are classified as Medium.          |
