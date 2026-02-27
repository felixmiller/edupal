import edupal


def test_basic_string_truth():
    wd = edupal.truth_table_to_wavedrom(['x0','x1','x2'], 'y', "00101100")
    assert "signal" in wd
    names = [s["name"] for s in wd["signal"]]
    assert names == ['x0','x1','x2','y']


def test_integer_truth():
    # 0b00101100 == 44, same truth table as above
    wd_str = edupal.truth_table_to_wavedrom(['x0','x1','x2'], 'y', "00101100")
    wd_int = edupal.truth_table_to_wavedrom(['x0','x1','x2'], 'y', 0b00101100)
    assert wd_str['signal'] == wd_int['signal']


def test_pre_post_context_wave_length():
    n_inputs = 3
    steps = 2 ** n_inputs
    pre, post = 2, 3
    wd = edupal.truth_table_to_wavedrom(['x0','x1','x2'], 'y', "00101100",
                                        pre_context=pre, post_context=post)
    expected_len = steps + pre + post
    # Wave strings may use dots for holds, so count non-dot characters
    out_wave = next(s['wave'] for s in wd['signal'] if s['name'] == 'y')
    assert len(out_wave) == expected_len


def test_set_linewidth():
    wd = edupal.truth_table_to_wavedrom(['x0'], 'y', "01")
    wd_lw = edupal.set_linewidth(wd, lw=3)
    for sig in wd_lw['signal']:
        assert sig['lw'] == 3
    # original should be unchanged
    for sig in wd['signal']:
        assert 'lw' not in sig
