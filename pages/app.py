"""Page objects for Actual Budget. Tests talk to these, never to raw selectors.

Selector policy (most to least stable): data-testid > ARIA role + name > visible text.
CSS classes are never used: Actual's are generated and change between releases.
"""
import re

from playwright.sync_api import Page, expect


def money(text: str) -> float:
    return float(text.strip().replace(",", "").replace("−", "-"))


class LoginPage:
    def __init__(self, page: Page, base_url: str):
        self.page, self.base_url = page, base_url

    def set_first_password(self, password: str):
        self.page.goto(self.base_url + "/")
        self.page.get_by_placeholder("Password", exact=True).fill(password)
        self.page.get_by_placeholder("Confirm password").fill(password)
        self.page.get_by_role("button", name="OK").click()

    def login(self, password: str):
        self.page.goto(self.base_url + "/login")
        self.page.locator("input[type=password]").fill(password)
        self.page.keyboard.press("Enter")

    def start_new_budget(self) -> "BudgetPage":
        self.page.get_by_text("Start budgeting").click(timeout=30_000)
        expect(self.page.get_by_text("To Budget:").first).to_be_visible(timeout=120_000)
        return BudgetPage(self.page)


class Sidebar:
    def __init__(self, page: Page):
        self.page = page

    def add_account(self, name: str, balance: str, off_budget: bool = False) -> "AccountPage":
        self.page.get_by_text("Add account").first.click()
        self.page.get_by_text("Create a local account").first.click()
        self.page.locator("input[name=name]").fill(name)
        if off_budget:
            self.page.locator("input[name=offbudget]").check()
        self.page.locator("input[name=balance]").fill(balance)
        self.page.locator("[role=dialog]").last.get_by_role("button", name="Create").click()
        expect(self.page.locator("input[name=name]")).to_have_count(0)
        return AccountPage(self.page, name)

    def account_balance(self, name: str) -> float:
        """Balance shown next to the account in the sidebar."""
        self.page.wait_for_timeout(300)   # balances are recomputed asynchronously after a write
        return money(self.page.evaluate("""name => [...document.querySelectorAll('[data-testid^="__global!balance-"]')]
            .filter(e => !e.dataset.testid.includes('-query-'))
            .find(e => e.closest('a') && e.closest('a').innerText.split('\\n')[0].trim() === name).innerText""", name))

    def open_account(self, name: str) -> "AccountPage":
        self.page.get_by_text(name, exact=True).first.click()
        expect(self.page.get_by_role("button", name="Add New")).to_be_visible()
        return AccountPage(self.page, name)

    def open_budget(self) -> "BudgetPage":
        self.page.get_by_text("Budget", exact=True).first.click()
        expect(self.page.get_by_text("To Budget:").first).to_be_visible()
        return BudgetPage(self.page)


class AccountPage(Sidebar):
    def __init__(self, page: Page, name: str):
        super().__init__(page)
        self.name = name

    def add_transaction(self, date: str, payee: str, amount: str, category: str | None = None,
                        deposit: bool = False, transfer_to: str | None = None):
        p, k = self.page, self.page.keyboard
        step = lambda: p.wait_for_timeout(250)                 # the grid moves focus asynchronously
        p.get_by_role("button", name="Add New").click(); step()
        k.press("Control+A"); k.type(date, delay=30); step(); k.press("Tab"); step()
        if transfer_to:
            k.type(transfer_to, delay=40); p.wait_for_timeout(500)
            # the dropdown offers "Create payee <x>" first; the account itself is listed under "Transfer To/From"
            p.get_by_test_id(f"{transfer_to}-payee-item").click()
            step()
            k.press("Tab"); step()                             # payee -> notes
        else:
            k.type(payee, delay=30); step(); k.press("Tab"); step()
        k.press("Tab"); step()                                 # notes -> category
        if category:
            k.type(category, delay=40); p.wait_for_timeout(400); k.press("Enter"); step()
        k.press("Tab"); step()                                 # -> payment
        if deposit:
            k.press("Tab"); step()                             # -> deposit
        k.type(amount, delay=30); step()
        p.get_by_role("button", name="Add", exact=True).click()
        p.wait_for_timeout(800)            # let the row commit; Escape too early discards it
        for _ in range(2):
            k.press("Escape")
        p.wait_for_timeout(300)

    def rows(self):
        return self.page.get_by_test_id("row")

    def row_with(self, text: str):
        return self.rows().filter(has_text=text).first

    def header_balance(self) -> float:
        return money(self.page.get_by_test_id("account-balance").inner_text())

    def cell(self, row_text: str, column: str):
        """column: date | payee | notes | category | debit | credit"""
        return self.row_with(row_text).get_by_test_id(column)

    def delete(self, row_text: str):
        self.row_with(row_text).get_by_test_id("select").click()
        self.page.get_by_role("button", name="1 transaction").click()
        self.page.get_by_text("Delete", exact=True).first.click()              # bulk-action menu
        self.page.locator("[role=dialog]").get_by_role("button", name="Delete").click()   # confirmation
        self.page.wait_for_timeout(500)

    def search(self, text: str):
        self.page.get_by_placeholder("Search").fill(text)
        self.page.wait_for_timeout(600)


class BudgetPage(Sidebar):
    def to_budget(self) -> float:
        months = self.page.evaluate("""() => [...document.querySelectorAll('[data-testid$="!available-funds"]')]
                                         .map(e => e.dataset.testid.slice(6, 12))""")
        values = self.page.evaluate("""() => [...document.querySelectorAll('*')]
            .filter(e => e.childElementCount == 0 && /^(To Budget|Overbudgeted):$/.test(e.textContent.trim()))
            .map(e => e.parentElement.innerText.split('\\n').pop())""")
        current = self.page.evaluate("() => document.querySelector('[data-testid=\"budget-table\"]') && "
                                     "[...document.querySelectorAll('[data-testid*=\"!sum-amount-\"]')][0]"
                                     ".dataset.testid.slice(6, 12)")
        return money(values[months.index(current)])

    def category(self, name: str):
        return self.page.get_by_test_id("row").filter(
            has=self.page.get_by_test_id("category-name").get_by_text(name, exact=True)).first

    def spent(self, name: str) -> float:
        return money(self.category(name).get_by_test_id("spent").inner_text())

    def assign(self, name: str, amount: str):
        self.category(name).get_by_test_id("budget").click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.type(amount, delay=30)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(500)
