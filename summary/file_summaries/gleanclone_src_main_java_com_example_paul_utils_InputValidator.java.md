# Summary of InputValidator.java

1. The primary purpose of this class:
   The `InputValidator` class is a utility class in the Spring Boot application that is used to validate various types of inputs related to accounts and transactions. It validates search criteria, account numbers, account creation criteria, and transaction search criteria.

2. Key Spring annotations used:
   This class does not use any Spring-specific annotations like `@Component`, `@Service`, `@Controller`, etc.

3. Dependencies and autowired components:
   There are no dependencies or autowired components in this class. However, it uses static constants from the `constants` class for validation.

4. Public methods and their functionality:
   - `isSearchCriteriaValid(AccountInput accountInput)`: This method validates the search criteria for an account. It checks if the sort code and account number match the patterns defined in the `constants` class.
   - `isAccountNoValid(String accountNo)`: This method validates an account number. It checks if the account number matches the pattern defined in the `constants` class.
   - `isCreateAccountCriteriaValid(CreateAccountInput createAccountInput)`: This method validates the criteria for creating an account. It checks if the bank name and owner name are not blank.
   - `isSearchTransactionValid(TransactionInput transactionInput)`: This method validates the search criteria for a transaction. It checks if the source and target accounts are valid and different from each other.

5. Relationships with other components:
   This class does not directly interact with other components. However, it can be used by other components in the application that require input validation. The `AccountInput`, `CreateAccountInput`, and `TransactionInput` classes are used as inputs to the validation methods, and the `constants` class is used for pattern matching.