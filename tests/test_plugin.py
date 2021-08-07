class TestPlugin:
    def test_list(self, mocker) -> None:
        msg = mocker.get_one_reply("/list")
        assert "❌" in msg.text

    def test_play(self, mocker) -> None:
        msg = mocker.get_one_reply("/play 1")
        assert "❌" in msg.text
