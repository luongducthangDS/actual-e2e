"""User journeys through the real UI. Each test = one thing a user wants to get done."""
import re

from conftest import PASSWORD
from playwright.sync_api import expect

from pages.app import LoginPage

DAY = "10/15/2026"


def test_first_run_owner_sets_password_and_reaches_budget(page, server):
    login = LoginPage(page, server.url)
    login.set_first_password(PASSWORD)
    expect(page).to_have_url(re.compile("/login$"))     # setting the password does not log you in
    login.login(PASSWORD)
    budget = login.start_new_budget()
    assert budget.to_budget() == 0.0


def test_wrong_password_is_rejected_then_right_one_works(page, server):
    login = LoginPage(page, server.url)
    login.set_first_password(PASSWORD)
    login.login("not-the-password")
    expect(page.get_by_text(re.compile("invalid password", re.IGNORECASE))).to_be_visible()
    login.login(PASSWORD)
    expect(page.get_by_text("Start budgeting")).to_be_visible()


def test_new_account_appears_in_sidebar_and_to_budget(budget):
    budget.add_account("Checking", "1,250.50")
    assert budget.account_balance("Checking") == 1250.50
    assert budget.open_budget().to_budget() == 1250.50


def test_categorised_expense_shows_up_in_budget(budget):
    account = budget.add_account("Checking", "1000")
    account.add_transaction(DAY, "Supermarket", "84.20", category="Food")
    assert account.account_balance("Checking") == 915.80
    assert account.open_budget().spent("Food") == -84.20


def test_transfer_moves_money_without_changing_to_budget(budget):
    budget.add_account("Checking", "1000")
    budget.add_account("Savings", "0")
    before = budget.open_budget().to_budget()
    account = budget.open_account("Checking")
    account.add_transaction(DAY, "", "300", transfer_to="Savings")
    assert account.account_balance("Checking") == 700.0
    assert account.account_balance("Savings") == 300.0
    assert account.open_budget().to_budget() == before


def test_editing_an_amount_recalculates_the_balance(budget):
    account = budget.add_account("Checking", "1000")
    account.add_transaction(DAY, "Cafe", "50")
    row = account.row_with("Cafe")
    row.get_by_test_id("debit").click()
    page = account.page
    page.keyboard.press("Control+A"); page.keyboard.type("80"); page.keyboard.press("Enter")
    page.wait_for_timeout(500)
    assert account.account_balance("Checking") == 920.0


def test_deleting_a_transaction_restores_the_balance(budget):
    account = budget.add_account("Checking", "1000")
    account.add_transaction(DAY, "Gym", "45")
    assert account.account_balance("Checking") == 955.0
    account.delete("Gym")
    assert account.account_balance("Checking") == 1000.0
    expect(account.row_with("Gym")).to_have_count(0)


def test_search_filters_the_register(budget):
    account = budget.add_account("Checking", "1000")
    account.add_transaction(DAY, "Bookshop", "20")
    account.add_transaction(DAY, "Bakery", "5")
    account.search("Book")
    expect(account.row_with("Bookshop")).to_be_visible()
    expect(account.row_with("Bakery")).to_have_count(0)


def test_data_survives_a_page_reload(budget):
    account = budget.add_account("Checking", "1000")
    account.add_transaction(DAY, "Pharmacy", "12.30")
    account.page.reload()
    expect(account.page.get_by_text("Pharmacy")).to_be_visible(timeout=60_000)
    assert account.account_balance("Checking") == 987.70
