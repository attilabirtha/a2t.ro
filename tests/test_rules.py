import unittest

from a2t_budget_control.models import CampaignRow, Policy
from a2t_budget_control.rules import recommend_for_campaign


class RulesTests(unittest.TestCase):
    def test_reduce_20_when_zero_conversion_value(self):
        rec = recommend_for_campaign(
            CampaignRow(
                campaign="X",
                channel="Video",
                status="ENABLED",
                daily_budget=1000,
                spend_7d=3000,
                spend_30d=15000,
                conv_value_7d=0,
                conv_value_30d=0,
            ),
            account_under_pacing=False,
            policy=Policy(),
        )
        self.assertTrue(rec.recommendation.startswith("Reduce 20%"))
        self.assertEqual(rec.recommended_budget, 800)

    def test_hold_for_low_data(self):
        rec = recommend_for_campaign(
            CampaignRow(
                campaign="Y",
                channel="Search",
                status="ENABLED",
                daily_budget=500,
                spend_7d=100,
                spend_30d=500,
                conv_value_7d=100,
                conv_value_30d=300,
            ),
            account_under_pacing=False,
            policy=Policy(),
        )
        self.assertEqual(rec.recommendation, "Hold")


if __name__ == "__main__":
    unittest.main()
