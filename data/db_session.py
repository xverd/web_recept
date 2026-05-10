import sqlalchemy as sa
import sqlalchemy.orm as orm


SqlAlchemyBase = orm.declarative_base()
__factory = None


def global_init(db_file):
    global __factory
    if __factory:
        return

    engine = sa.create_engine(f"sqlite:///{db_file}?check_same_thread=False", echo=False)
    __factory = orm.scoped_session(orm.sessionmaker(bind=engine))

    from . import all_models

    SqlAlchemyBase.metadata.create_all(engine)


def create_session():
    return __factory()


def remove_session():
    if __factory:
        __factory.remove()
