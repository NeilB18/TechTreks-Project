import unittest
from datetime import date, datetime, timedelta
from itertools import count

from trip_model.activity import Activity
from trip_model.budget import Budget
from trip_model.category import Category
from trip_model.expense import Expense
from trip_model.money import split_proportional
from trip_model.person import Person
from trip_model.poll import Poll
from trip_model.reminder import Reminder
from trip_model.trip import Trip

expense_ids = count(1)

def make_expense(paid_by, amount_cents, category=Category.FOOD):
    return Expense(next(expense_ids), paid_by, amount_cents, "test", category)

def make_trip(*names):
    trip = Trip(1, "Spring Break")
    people = [Person(name, name.title(), f"chat-{name}", f"@{name}") for name in names]
    for person in people:
        trip.add_member(person)
    return trip, people


class TestExpenseSplits(unittest.TestCase):
    def setUp(self):
        self.x = Person("x", "X", "cx", "@x")

    def test_equal_split_including_payer(self):
        e = make_expense(self.x, 9000)
        self.assertEqual(e.split_equal(["x", "y", "z"]), {"x": 6000, "y": -3000, "z": -3000})

    def test_equal_split_payer_not_participant(self):
        e = make_expense(self.x, 9000)
        self.assertEqual(e.split_equal(["y", "z"]), {"x": 9000, "y": -4500, "z": -4500})

    def test_custom_split(self):
        e = make_expense(self.x, 1700)
        self.assertEqual(e.split_custom({"x": 800, "y": 600, "z": 300}),
                         {"x": 900, "y": -600, "z": -300})

    def test_equal_split_remainder_goes_to_first_ids(self):
        e = make_expense(self.x, 1000)
        e.split_equal(["z", "y", "x"])
        self.assertEqual([e.share_of(p) for p in ["x", "y", "z"]], [334, 333, 333])

    def test_percentage_split(self):
        e = make_expense(self.x, 1000)
        e.split_percentage({"x": 33.33, "y": 33.33, "z": 33.34})
        self.assertEqual([e.share_of(p) for p in ["x", "y", "z"]], [333, 333, 334])
        self.assertEqual(sum(e.splits.values()), 0)

    def test_percentage_must_sum_to_100(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_percentage({"x": 50, "y": 40})

    def test_custom_must_cover_whole_bill(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_custom({"y": 500})

    def test_duplicate_participants_rejected(self):
        with self.assertRaises(ValueError):
            make_expense(self.x, 1000).split_equal(["y", "y"])


class TestBudget(unittest.TestCase):
    def test_remaining_and_warning(self):
        trip, (a, b) = make_trip("a", "b")
        budget = Budget("a", 50000, {Category.DRINKS: 8000})
        e = make_expense(b, 15000, Category.DRINKS)
        e.split_equal(["a", "b"])  # a's share is 7500
        trip.add_expense(e)
        self.assertEqual(budget.remaining(Category.DRINKS, trip.expenses), 500)
        self.assertTrue(budget.warning(Category.DRINKS, trip.expenses))

    def test_planned_costs_count_toward_warning(self):
        budget = Budget("a", 50000, {Category.ACTIVITIES: 14000})
        self.assertFalse(budget.warning(Category.ACTIVITIES, []))
        self.assertFalse(budget.warning(Category.ACTIVITIES, [], planned_cents=10000))
        self.assertTrue(budget.warning(Category.ACTIVITIES, [], planned_cents=13333))

    def test_no_limit_returns_none(self):
        budget = Budget("a", 50000, {})
        self.assertIsNone(budget.remaining(Category.FOOD, []))
        self.assertFalse(budget.warning(Category.FOOD, []))


class TestTripLedger(unittest.TestCase):
    def test_balances_and_settlement_excluded_from_spending(self):
        trip, (x, y, z) = make_trip("x", "y", "z")
        e = make_expense(x, 9000)
        e.split_equal(["x", "y", "z"])
        trip.add_expense(e)
        self.assertEqual(trip.balances(), {"x": 6000, "y": -3000, "z": -3000})

        trip.record_settlement("y", "x", 3000, "pay-1")
        self.assertEqual(trip.balances(), {"x": 3000, "y": 0, "z": -3000})
        self.assertEqual(trip.spent_by_category()[Category.FOOD], 9000)
        self.assertNotIn(Category.SETTLEMENT, trip.spent_by_category())
        self.assertEqual(trip.spent_by_category(y)[Category.FOOD], 3000)
        self.assertEqual(trip.settlement_plan(), [("z", "x", 3000)])

    def test_settlement_idempotent(self):
        trip, _ = make_trip("x", "y")
        trip.record_settlement("y", "x", 100, "pay-1")
        with self.assertRaises(ValueError):
            trip.record_settlement("y", "x", 100, "pay-1")

    def test_expense_with_non_member_rejected(self):
        trip, (x, _) = make_trip("x", "y")
        e = make_expense(x, 1000)
        e.split_equal(["x", "stranger"])
        with self.assertRaises(ValueError):
            trip.add_expense(e)

    def test_greedy_settlements_pairs_exact_opposites_first(self):
        trip, _ = make_trip()
        # a and b cancel exactly, so they settle directly and c covers d and e: 3 payments.
        b = {"a": -500, "b": 500, "c": -700, "d": 300, "e": 400}
        payments = trip._greedy_settlements(b)
        self.assertEqual(payments, [("a", "b", 500), ("c", "e", 400), ("c", "d", 300)])

    def test_greedy_settlements_clears_everyone(self):
        trip, _ = make_trip()
        b = {"a": -1000, "b": -600, "c": 900, "d": 500, "e": 200}
        payments = trip._greedy_settlements(b)
        self.assertLessEqual(len(payments), len(b) - 1)
        net = dict.fromkeys(b, 0)
        for debtor, creditor, amount in payments:
            self.assertLess(b[debtor], 0)
            self.assertGreater(b[creditor], 0)
            net[debtor] += amount
            net[creditor] -= amount
        self.assertEqual({p: -v for p, v in net.items()}, b)

    def test_empty_plan(self):
        trip, _ = make_trip("x", "y")
        self.assertEqual(trip.settlement_plan(), [])


class TestPlanning(unittest.TestCase):
    def test_itinerary_by_day(self):
        trip, (x, _) = make_trip("x", "y")
        day = datetime(2027, 3, 10, 9)
        late = Activity(2, "Dinner", "Downtown", day + timedelta(hours=10),
                        day + timedelta(hours=12), 3000, True, [x], False, None)
        early = Activity(1, "Hike", "Trail", day, day + timedelta(hours=3),
                         0, False, [x], True, None)
        trip.add_activity(late)
        trip.add_activity(early)
        self.assertEqual(trip.itinerary_by_day(), {day.date(): [early, late]})

    def test_poll_ties_and_closing(self):
        poll = Poll(1, "Where?", ["Miami", "Denver"])
        self.assertEqual(poll.winner(), [])
        poll.vote("x", "Miami")
        poll.vote("y", "Denver")
        self.assertEqual(poll.winner(), ["Miami", "Denver"])
        poll.vote("y", "Miami")
        self.assertEqual(poll.winner(), ["Miami"])

        closed = Poll(2, "When?", ["March"], closes_at=datetime.now() - timedelta(minutes=1))
        with self.assertRaises(ValueError):
            closed.vote("x", "March")

    def test_reminder_validation(self):
        with self.assertRaises(ValueError):
            Reminder("Pack!", datetime.now(), created_by="bob")
        self.assertEqual(Reminder("Pack!", datetime.now(), created_by="agent").created_by, "agent")
        r = Reminder("Pack!", datetime.now() - timedelta(minutes=1))
        self.assertTrue(r.is_due())
        r.mark_sent()
        self.assertFalse(r.is_due())


    def test_activity_optional_fields_and_per_person_cost(self):
        trip, (x, y) = make_trip("x", "y")
        boat = Activity("boat", "Boat tour", start=date(2027, 3, 15), est_cost_cents=40000,
                        cost_is_per_person=False, attendees=[x, y])
        self.assertEqual(boat.est_per_person_cents(), 20000)
        self.assertIsNone(Activity("free", "Beach day").est_per_person_cents())
        with self.assertRaises(ValueError):
            boat.update(end=datetime(2027, 3, 14, 18))
        self.assertIsNone(boat.end)  # a rejected edit changes nothing
        trip.add_activity(boat)
        trip.remove_member("y")
        self.assertEqual(boat.est_per_person_cents(), 40000)

    def test_poll_uses_the_given_time_and_explains_bad_votes(self):
        poll = Poll(1, "Where?", ["Miami", "Denver"], closes_at=datetime(2027, 3, 1, 12))
        poll.vote("x", "Miami", now=datetime(2027, 3, 1, 11))
        with self.assertRaisesRegex(ValueError, "isn't an option"):
            poll.vote("x", "Boston", now=datetime(2027, 3, 1, 11))
        with self.assertRaisesRegex(ValueError, "closed"):
            poll.vote("y", "Denver", now=datetime(2027, 3, 1, 12))
        self.assertFalse(poll.is_open)


class TestRefunds(unittest.TestCase):
    def test_refund_goes_back_by_share_and_updates_balances_and_spending(self):
        trip, (a, b, c) = make_trip("a", "b", "c")
        e = make_expense(a, 30000, Category.ACTIVITIES)
        e.split_equal(["a", "b", "c"])
        trip.add_expense(e)
        trip.record_settlement("b", "a", 10000, "pay-1")
        refund = trip.add_refund(e.id, "r1", 15000, note="Concert moved")
        self.assertEqual(refund.per_person, {"a": 5000, "b": 5000, "c": 5000})
        self.assertEqual(e.shares(), {"a": 10000, "b": 10000, "c": 10000})  # before refunds
        self.assertEqual(e.share_of("c"), 5000)                             # after refunds
        self.assertEqual(trip.balances(), {"a": 0, "b": 5000, "c": -5000})
        self.assertEqual(trip.settlement_plan(), [("c", "b", 5000)])
        self.assertEqual(Budget("c", 50000).spent(Category.ACTIVITIES, trip.expenses), 5000)
        self.assertEqual(trip.spent_by_category()[Category.ACTIVITIES], 15000)
        self.assertEqual(trip.refunds, [refund])

    def test_refund_limits(self):
        trip, (a, b) = make_trip("a", "b")
        e = make_expense(a, 10000)
        e.split_equal(["a", "b"])
        trip.add_expense(e)
        trip.add_refund(e.id, "r1", 6000)
        with self.assertRaisesRegex(ValueError, "more than the expense"):
            trip.add_refund(e.id, "r2", 4001)
        with self.assertRaises(ValueError):
            trip.add_refund(e.id, "r1", 100)  # same refund id twice
        payback = trip.record_settlement("b", "a", 1000, "pay-1")
        with self.assertRaisesRegex(ValueError, "Paybacks can't be refunded"):
            trip.add_refund(payback.id, "r3", 500)

    def test_deleting_an_expense_takes_its_refunds_and_unlinks_activities(self):
        trip, (a, b) = make_trip("a", "b")
        e = make_expense(a, 10000)
        e.split_equal(["a", "b"])
        trip.add_expense(e)
        trip.add_refund(e.id, "r1", 2000)
        trip.add_activity(Activity("dinner", "Dinner", attendees=[a, b], expense_id=e.id))
        trip.delete_expense(e.id)
        self.assertEqual((trip.refunds, trip.activities[0].expense_id), ([], None))
        self.assertEqual(trip.balances(), {"a": 0, "b": 0})


class TestMembersAndOptOuts(unittest.TestCase):
    def test_dropout_keeps_past_splits_but_leaves_new_ones_and_activities(self):
        trip, (a, b, c) = make_trip("a", "b", "c")
        e = make_expense(a, 9000)
        e.split_equal(["a", "b", "c"])
        trip.add_expense(e)
        trip.add_activity(Activity("boat", "Boat tour", attendees=[a, b, c]))
        self.assertEqual(trip.remove_member("c"), ["boat"])
        self.assertEqual(trip.balances()["c"], -3000)  # still owes
        self.assertEqual(trip.active_member_ids(), ["a", "b"])
        with self.assertRaisesRegex(ValueError, "removed from the trip"):
            trip.split_people(["a", "c"], Category.FOOD)
        with self.assertRaisesRegex(ValueError, "already removed"):
            trip.remove_member("c")

    def test_split_people_applies_exclusions_opt_outs_and_overrides(self):
        trip, _ = make_trip("a", "b", "c", "d")
        trip.set_opt_out("b", Category.DRINKS)
        self.assertEqual(trip.split_people(["a", "b", "c", "d", "a"], Category.DRINKS, exclude={"d"}),
                         (["a", "c"], ["b"]))
        self.assertEqual(trip.split_people(["a", "b"], Category.DRINKS, overrides={"b"}), (["a", "b"], []))
        self.assertEqual(trip.split_people(["a", "b"], Category.FOOD), (["a", "b"], []))
        trip.remove_opt_out("b", Category.DRINKS)
        self.assertEqual(trip.split_people(["b"], Category.DRINKS), (["b"], []))
        with self.assertRaisesRegex(ValueError, "Nobody left"):
            trip.split_people(["a"], Category.FOOD, exclude={"a"})
        with self.assertRaisesRegex(ValueError, "not a member"):
            trip.split_people(["zed"], Category.FOOD)


class TestMoney(unittest.TestCase):
    def test_split_proportional_largest_remainder_then_id_order(self):
        self.assertEqual(split_proportional(10000, {"b": 1, "a": 1, "c": 1}), {"b": 3333, "a": 3334, "c": 3333})
        self.assertEqual(split_proportional(101, {"x": 3, "y": 1}), {"x": 76, "y": 25})
        with self.assertRaises(ValueError):
            split_proportional(100, {"x": 0})


if __name__ == "__main__":
    unittest.main()
