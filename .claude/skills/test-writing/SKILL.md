---
name: test-writing
description: Writes tests. Use when creating new tests or when modifying the existing tests, you can also reference it when you need to review the test code in a pull request.
---
Test are located under @tests/ folder, create a folder if there if it does not exist.
For tests that are require stored data use the test database with the same schema as the prodution database, create the test db if does not exist yet.

When wirting a test:
1. Use pytest
2. Try to use parametrised test instead of multiplying the same test to test it with different inputs.
3. Think about execution order of tests, they should not depend on previsouly executed tests, if some data needs to be prapaired for the specific test, use fixture and clean it after the test is executed.
4. Do not store the records to the database inside the body of the test, if you need prepaired data, create a fixture and use it in the test.
