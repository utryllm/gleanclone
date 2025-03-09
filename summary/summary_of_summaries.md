# Application Overview

Application Overview:

The Spring Boot application is designed to simulate an online banking system. It is structured around the Model-View-Controller (MVC) architecture, with the `com` package serving as the root module.

The high-level architecture of the application is organized into several key components: Controllers, Services, Repositories, Models, Data Transfer Objects (DTOs), and Utility Classes. The Controllers (`AccountRestController.java` and `TransactionRestController.java`) handle incoming HTTP requests and interact with the Services (`AccountService.java` and `TransactionService.java`). The Services encapsulate the business logic related to accounts and transactions, and interact with the Repositories (`AccountRepository.java` and `TransactionRepository.java`) to perform database operations.

The Models (`Account.java` and `Transaction.java`) represent the data structure of a bank account and a transaction, respectively. The DTOs (`AccountInput.java`, `CreateAccountInput.java`, `TransactionInput.java`, `DepositInput.java`, and `WithdrawInput.java`) are used to encapsulate data for various operations. The Utility Classes (`CodeGenerator.java` and `InputValidator.java`) provide support functions such as generating random codes and validating inputs.

The primary data flow in the system starts from the Controllers, which receive HTTP requests and pass the data to the Services. The Services then use the Repositories to interact with the database, using the Models to map data. The Utility Classes and constants are used as needed throughout the application.

The application's main external interfaces are the REST APIs provided by the Controllers. These APIs allow other systems to interact with the application, perform operations on accounts and transactions, and access data from the database. The Controllers, Services, and Repositories also expose public methods that allow other components within the application to interact with them.

The application uses the Spring context to manage these components and their relationships. The `Application.java` class, serving as the entry point, starts the application and initializes the Spring context. The Spring context then manages the lifecycle of the components, including their instantiation, configuration, and destruction.