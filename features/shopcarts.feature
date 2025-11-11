Feature: Shopcart creation via admin UI
  Administrators should be able to create new shopcarts from the web console
  and immediately see the entries reflected in the list. Validation errors
  should surface without touching the REST API directly.

  Background:
    Given the shopcart admin UI is available

  Scenario: Successfully create a new shopcart
    Given I am a logged-in customer on the Shopcart page
    When I submit a valid "Create Cart" form with customer_id=101 and name="My Summer Cart"
    Then I should receive a confirmation message "Shopcart created successfully"
    And I should see the new cart listed with status "OPEN"

  Scenario: Invalid request body
    Given I am on the Create Shopcart form
    When I submit the form without entering a customer ID
    Then I should see an error message "Customer ID is required"
    And the cart should not be created

  Scenario: Delete a shopcart from the details panel
    Given a shopcart exists with customer id 321
    And I am a logged-in customer on the Shopcart page
    When I load the shopcart details for customer 321
    And I delete the shopcart from the details panel
    Then I should receive a confirmation message "Shopcart 321 deleted"
    And the cart details panel should be cleared

  Scenario: Deleting a missing shopcart surfaces an error
    Given a shopcart exists with customer id 654
    And I am a logged-in customer on the Shopcart page
    And I load the shopcart details for customer 654
    And the shopcart with customer id 654 is removed outside the UI
    When I delete the shopcart from the details panel
    Then I should see an error message "Cart not found"

  Scenario: Update an existing shopcart successfully
    Given there is an existing shopcart with customer_id=2 and status "OPEN"
    When I send a PUT request to update shopcart for customer 2 with status "LOCKED"
    Then I should receive a 200 OK response
    And the response body should include the updated status "LOCKED"
    And the shopcart data should match the updated status

  Scenario: Update a shopcart that does not exist
    Given there is no shopcart with customer_id=777
    When I send a PUT request to update shopcart for customer 777 with status "LOCKED"
    Then I should receive a 404 Not Found response
