from luxurywheels import db, app
from luxurywheels.models import Usuario, Veiculo, Aluguel, Pagamento, Reserva

with app.app_context():
    db.create_all()