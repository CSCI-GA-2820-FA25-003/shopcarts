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
    And I should see the new cart listed with status "ACTIVE"

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
    Given there is an existing shopcart with customer_id=2 and status "ACTIVE"
    When I send a PUT request to update shopcart for customer 2 with status "LOCKED"
    Then I should receive a 200 OK response in the UI
    And the response body should include the updated status "LOCKED"
    And the shopcart data should match the updated status

  Scenario: Update a shopcart that does not exist
    Given there is no shopcart with customer_id=777
    When I send a PUT request to update shopcart for customer 777 with status "LOCKED"
    Then I should receive a 404 Not Found response

  Scenario: View cart details from table using View Cart button
    Given a shopcart exists with customer id 555
    And I am a logged-in customer on the Shopcart page
    When I click the "View Cart" button for customer 555 in the table
    Then I should see the shopcart details displayed in the result card
    And the result card should show customer ID 555
    And the result card should show the cart status

  Scenario: Retrieve all shopcarts
    Given the shopcart admin UI is available
    And there is an existing shopcart with customer_id=101 and status "ACTIVE"
    And there is an existing shopcart with customer_id=102 and status "ABANDONED"
    When I open the "My Shopcarts" page
    Then I should see a list of all my shopcarts
    And each shopcart should show its ID, name, and status

  Scenario: Filter shopcarts by status
    Given the shopcart admin UI is available
    And there is an existing shopcart with customer_id=201 and status "ACTIVE"
    And there is an existing shopcart with customer_id=202 and status "ABANDONED"
    When I filter by "ACTIVE"
    Then I should see only the shopcarts with status "ACTIVE"

  Scenario: Invalid filter parameter
    Given the shopcart admin UI is available
    When I try to apply a filter that doesn't exist
    Then I should see an error message "Invalid filter option"

  Scenario: UI shows empty state
    Given the shopcart admin UI is available
    And all shopcarts are deleted
    When I open the "My Shopcarts" page
    Then I should see a message "No shopcarts found"

  Scenario: Query shopcarts by customer ID
    Given shopcarts exist for customer_id=5
    When I send a GET request to "/shopcarts?customer_id=5"
    Then I should receive a 200 OK response
    And all returned shopcarts should have customer_id=5

  Scenario: Query shopcarts by status
    Given shopcarts exist with status="ACTIVE"
    When I send a GET request to "/shopcarts?status=ACTIVE"
    Then I should receive a 200 OK response
    And all returned shopcarts should have status="ACTIVE"

  Scenario: Query shopcarts by price range
    Given shopcarts exist with various total prices
    When I send a GET request to "/shopcarts?min_total=50.0&max_total=200.0"
    Then I should receive a 200 OK response
    And all returned shopcarts should have total_price between 50.0 and 200.0

  Scenario: Query with invalid parameter
    Given the service is running
    When I send a GET request to "/shopcarts?status=INVALID_STATUS"
    Then I should receive a 400 Bad Request response

  # ============================================================================
  # LOCK/EXPIRE OPERATIONS - Backend API
  # ============================================================================
  Scenario: Successfully lock a cart
    Given an active shopcart exists for customer 101
    When I send a PATCH request to "/shopcarts/101/lock"
    Then I should receive a 200 OK response
    And the cart's status should update to "locked"
    And the last_modified timestamp should change

  Scenario: Successfully expire a cart
    Given a shopcart exists for customer 202
    When I send a PATCH request to "/shopcarts/202/expire"
    Then I should receive a 200 OK response
    And the cart's status should update to "expired"
    And the last_modified timestamp should change

  Scenario: Attempt to lock a non-existent cart
    Given there is no shopcart with customer_id=999
    When I send a PATCH request to "/shopcarts/999/lock"
    Then I should receive a 404 Not Found response
    And the response should state the shopcart was not found

  Scenario: Attempt to expire a non-existent cart
    Given there is no shopcart with customer_id=888
    When I send a PATCH request to "/shopcarts/888/expire"
    Then I should receive a 404 Not Found response
    And the response should state the shopcart was not found

  # ============================================================================
  # LOCK/EXPIRE OPERATIONS - Frontend UI
  # ============================================================================
  Scenario: UI locks cart successfully
    Given I am viewing the shopcart management list in the Admin UI
    And a cart for customer "101" with status "active" is visible
    When I click the "Lock" button for that cart
    Then the cart's status should immediately change to "locked" in the table
    And I should see a toast notification saying "Cart locked successfully"

  Scenario: UI expires cart successfully
    Given I am viewing the shopcart management list in the Admin UI
    And a cart for customer "202" with status "active" is visible
    When I click the "Expire" button for that cart
    Then the cart's status should immediately change to "expired" in the table
    And I should see a toast notification saying "Cart expired successfully"

  Scenario: UI shows error for invalid action (e.g., cart not found)
    Given I am viewing the shopcart management list
    And I am about to click "Lock" for customer "999"
    And another admin deletes that cart just before I click
    When I click the "Lock" button for cart "999"
    Then I should see an error message saying "Error: Cart not found"
    And the cart for "999" should be removed from the list

  # ============================================================================
  # SHOPCART TOTALS - Backend API
  # ============================================================================
  Scenario: Retrieve totals for a populated cart
    Given a shopcart for customer 101 contains multiple items
    When I send a GET request to "/shopcarts/101/totals"
    Then I should receive a 200 OK response
    And the response includes item_count, total_quantity, subtotal, discount, and total with correct values

  Scenario: Retrieve totals for an empty cart
    Given a shopcart for customer 202 exists but has no items
    When I send a GET request to "/shopcarts/202/totals"
    Then I should receive a 200 OK response
    And the response shows zeros for item_count, total_quantity, subtotal, discount, and total

  Scenario: Attempt to retrieve totals for a missing cart
    Given no shopcart exists for customer 999
    When I send a GET request to "/shopcarts/999/totals"
    Then I should receive a 404 Not Found response
    And the response should state the shopcart was not found

  # ============================================================================
  # SHOPCART TOTALS - Frontend UI
  # ============================================================================
  Scenario: UI displays correct totals for a populated cart
    Given I am viewing my shopcart page in the UI
    And my cart contains one item priced at "10.00" with quantity 2
    When the "Cart Summary" component loads
    Then the "Subtotal" should display "20.00"
    And the "Total" should display "20.00"
    And the "Total Items" should display "2"

  Scenario: UI displays zero totals for an empty cart
    Given I am viewing my shopcart page in the UI
    And my cart is empty
    When the "Cart Summary" component loads
    Then the "Subtotal" should display "0.00"
    And the "Total" should display "0.00"
    And the "Total Items" should display "0"

  Scenario: UI totals update automatically when item quantity changes
    Given the shopcart admin UI is available
    Given I am viewing my shopcart page and the "Total" is "10.00"
    When I change the quantity of an item, causing the total to update
    Then the "Total" should immediately change to the new calculated total (e.g., "20.00") without a page refresh
    And the "Subtotal" should also update immediately

  Scenario: UI shows an error if totals fail to load
    Given I am viewing my shopcart page in the UI
    And my session has expired (cart 999 is no longer found)
    When the "Cart Summary" component tries to load data
    Then I should see an error message in the summary area saying "Could not load totals"
    And the "Total" should display "N/A" or be hidden

