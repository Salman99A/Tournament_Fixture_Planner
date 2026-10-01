"""
seed.py — Interdepartmental Cup 2.0 Demo Data
Run: python seed.py
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app import app
from models import db, Tournament, Team, Match, StandingEntry, init_event_data
from routes.tournament_routes import _generate_round_robin, _generate_knockout, _init_standings
from routes.match_routes import _update_standings


def clean_db():
    with app.app_context():
        StandingEntry.query.delete()
        Match.query.delete()
        Team.query.delete()
        Tournament.query.delete()
        db.session.commit()
        init_event_data()
        print("✨ Database cleaned: All demo tournaments, teams, matches, and standings removed.")
        print("⚙️ Configured Sports & Departments preserved for Admin setup.")


def seed_demo():
    with app.app_context():
        db.drop_all()
        db.create_all()
        init_event_data()

        # 1. Cricket Boys — Round Robin (5 teams: odd count, tests byes + standings)
        t1 = Tournament(
            name="Interdepartmental Cricket Cup (Boys)",
            format="round_robin",
            sport_type="cricket",
            gender="Boys",
            department="All",
            result_mode="winner_only",
            status="active",
            points_win=2, points_draw=1, points_loss=0, draws_allowed=True,
        )
        db.session.add(t1); db.session.flush()
        teams1 = _add_teams(t1, [
            ("CSE Warriors", "CSE", "Boys", "cricket", None),
            ("IT Titans", "IT", "Boys", "cricket", None),
            ("AIML Strikers", "AIML", "Boys", "cricket", None),
            ("CSBS Challengers", "CSBS", "Boys", "cricket", None),
            ("EXTC Kings", "EXTC", "Boys", "cricket", None),
        ])
        _generate_round_robin(t1, teams1)
        _init_standings(t1, teams1)
        db.session.commit()
        # Simulate Round 1 results (1 win, 1 tie)
        _sim_winner_only_results(t1, 1, [(0, 'win'), (1, 'tie')])
        print("✅ Cricket (Boys RR, 5 teams, R1 played: CSE Warriors, IT Titans, ...)")

        # 2. Football Boys — Round Robin (4 teams)
        t2 = Tournament(
            name="Interdepartmental Football Trophy (Boys)",
            format="round_robin",
            sport_type="football",
            gender="Boys",
            department="All",
            result_mode="score_based",
            status="active",
            points_win=3, points_draw=1, points_loss=0, draws_allowed=True,
        )
        db.session.add(t2); db.session.flush()
        teams2 = _add_teams(t2, [
            ("AIML FC", "AIML", "Boys", "football", None),
            ("CSE United", "CSE", "Boys", "football", None),
            ("EXTC Tigers", "EXTC", "Boys", "football", None),
            ("IT Dynamos", "IT", "Boys", "football", None),
        ])
        _generate_round_robin(t2, teams2)
        _init_standings(t2, teams2)
        db.session.commit()
        # Simulate Round 1 results
        _sim_score_results(t2, 1, [(3, 1), (2, 2)])
        print("✅ Football (Boys RR, 4 teams, R1 played: AIML FC, CSE United, ...)")

        # 3. Volleyball Girls — Knockout (4 teams)
        t3 = Tournament(
            name="Interdepartmental Volleyball Championship (Girls)",
            format="knockout",
            sport_type="volleyball",
            gender="Girls",
            department="All",
            result_mode="score_based",
            status="active",
            points_win=2, points_draw=0, points_loss=0, draws_allowed=False,
        )
        db.session.add(t3); db.session.flush()
        teams3 = _add_teams(t3, [
            ("CSBS Volleyball", "CSBS", "Girls", "volleyball", None),
            ("CSE Spikers", "CSE", "Girls", "volleyball", None),
            ("IT Smashers", "IT", "Girls", "volleyball", None),
            ("EXTC Queens", "EXTC", "Girls", "volleyball", None),
        ])
        _generate_knockout(t3, teams3)
        db.session.commit()
        print("✅ Volleyball (Girls KO, 4 teams: CSBS Volleyball, CSE Spikers, ...)")

        # 4. Chess Boys — Knockout (4 teams / players with player names)
        t4 = Tournament(
            name="Interdepartmental Chess Championship (Boys)",
            format="knockout",
            sport_type="chess",
            gender="Boys",
            department="All",
            result_mode="winner_only",
            status="active",
            points_win=2, points_draw=1, points_loss=0, draws_allowed=True,
        )
        db.session.add(t4); db.session.flush()
        teams4 = _add_teams(t4, [
            ("EXTC Chess", "EXTC", "Boys", "chess", "Rahul Sharma"),
            ("CSE Grandmasters", "CSE", "Boys", "chess", "Aman Gupta"),
            ("AIML Knights", "AIML", "Boys", "chess", "Priya Verma"),
            ("IT Rooks", "IT", "Boys", "chess", "Karan Patel"),
        ])
        _generate_knockout(t4, teams4)
        db.session.commit()
        print("✅ Chess (Boys KO, 4 participants: EXTC Chess [Rahul Sharma], ...)")

        # 5. Kabaddi Boys — Setup Stage (4 teams, awaiting fixtures)
        t5 = Tournament(
            name="Interdepartmental Kabaddi League (Boys)",
            format="round_robin",
            sport_type="kabaddi",
            gender="Boys",
            department="All",
            result_mode="score_based",
            status="setup",
            points_win=3, points_draw=1, points_loss=0, draws_allowed=True,
        )
        db.session.add(t5); db.session.flush()
        _add_teams(t5, [
            ("CSE Raiders", "CSE", "Boys", "kabaddi", None),
            ("IT Defenders", "IT", "Boys", "kabaddi", None),
            ("AIML Warriors", "AIML", "Boys", "kabaddi", None),
            ("CSBS Lions", "CSBS", "Boys", "kabaddi", None),
        ])
        db.session.commit()
        print("✅ Kabaddi (Boys RR, setup stage, 4 teams ready for fixture generation)")

        print("\n🎉 Interdepartmental Cup 2.0 Seed Complete! Run: python app.py → http://localhost:5000")


def _add_teams(tournament, team_tuples):
    teams = []
    for item in team_tuples:
        name, dept, gender, sport, player = item
        t = Team(
            name=name,
            name_key=name.strip().lower(),
            tournament_id=tournament.id,
            department=dept,
            gender=gender,
            sport_type=sport,
            player_name=player,
        )
        db.session.add(t)
        teams.append(t)
    db.session.flush()
    return teams


def _sim_score_results(tournament, round_num, results):
    matches = Match.query.filter_by(
        tournament_id=tournament.id, round_number=round_num, is_bye=False
    ).order_by(Match.match_number).all()
    for match, (s1, s2) in zip(matches, results):
        match.team1_score = s1; match.team2_score = s2
        match.result_type = None; match.status = 'completed'
        match.winner_id = (
            match.team1_id if s1 > s2 else
            match.team2_id if s2 > s1 else None
        )
        db.session.flush()
        _update_standings(tournament, match)
    db.session.commit()


def _sim_winner_only_results(tournament, round_num, results):
    matches = Match.query.filter_by(
        tournament_id=tournament.id, round_number=round_num, is_bye=False
    ).order_by(Match.match_number).all()
    for match, (winner_idx, result_type) in zip(matches, results):
        match.team1_score = None; match.team2_score = None
        match.result_type = result_type; match.status = 'completed'
        match.winner_id = (
            match.team1_id if result_type == 'win' and winner_idx == 0 else
            match.team2_id if result_type == 'win' and winner_idx == 1 else None
        )
        db.session.flush()
        _update_standings(tournament, match)
    db.session.commit()


if __name__ == '__main__':
    if '--demo' in sys.argv:
        seed_demo()
    else:
        clean_db()
