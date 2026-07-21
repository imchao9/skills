import hashlib
import json
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parent.parent


def sha256(relative_path):
    return hashlib.sha256((SKILL_ROOT / relative_path).read_bytes()).hexdigest()


class SkillContractTests(unittest.TestCase):
    def test_existing_learning_contracts_and_publisher_are_unchanged(self):
        expected = {
            "references/resolution-contract.md": (
                "b9a9873aae576c2d127517b044db39d986d16f81d2b52eee69f75fe3b50eabbd"
            ),
            "references/teaching-contract.md": (
                "794bbc89edf46f61b7b45f4714932ea734ac89800989de82ca99b4a6679a7749"
            ),
            "scripts/publish.py": (
                "35ec91a7f1435bab133ff77a214ad572ee774d2a9f579e935ded54ceec9c3dc5"
            ),
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(sha256(path), digest)

    def test_process_contract_is_independent_and_has_approved_shape(self):
        contract = (SKILL_ROOT / "references/process-contract.md").read_text(
            encoding="utf-8"
        )
        required = (
            "每次运行都生成一份过程文档",
            "它独立于学习总结",
            "1. `需求与背景`",
            "2. `技术方案`",
            "3. `关键判断与处理`",
            "没有实质内容时省略",
            "yyyy-MM-dd-{中文主题}-过程.md",
            "不读取或复用学习总结的主题",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract)
        self.assertIn(
            "不得添加独立的`实施过程`、`完成情况`、`验证与结果`或`未决事项`章节",
            contract,
        )
        for removed_heading in ("实施过程", "完成情况", "验证与结果", "未决事项"):
            with self.subTest(heading=removed_heading):
                self.assertNotIn(f"\n## {removed_heading}\n", contract)

    def test_main_workflow_reviews_separately_and_authorizes_once(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required = (
            "过程文档不得改变学习总结的生成规则",
            "不符合时，说明依据并只跳过学习总结，不结束本次运行",
            "逐份展示完整 Markdown 和临时路径，并分别询问是否准确、满意",
            "列出本次待发布的全部文件，统一询问用户是否明确授权发布",
            "不撤销已经成功发布的其他文件",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_humanizer_reference_is_the_approved_verbatim_snapshot(self):
        self.assertEqual(
            sha256("references/humanizer-zh.md"),
            "e0edbdbc9008644263d5573fb59beac95794e188fd99c35012bfd79e9ae4beeb",
        )

    def test_gitlab_target_is_preserved(self):
        config = json.loads(
            (SKILL_ROOT / "references/gitlab-target.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config,
            {
                "repository_ssh_url": (
                    "git@gitlab.codemao.cn:"
                    "backend/platform-informatization/tool/skills.git"
                ),
                "branch": "main",
                "base_path": "learning",
            },
        )


if __name__ == "__main__":
    unittest.main()
